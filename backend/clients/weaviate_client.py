import math
import logging
import asyncio

from fastapi import HTTPException
from typing import Optional, List, Set, AsyncGenerator
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from weaviate.connect import ConnectionParams
from weaviate.classes.query import Filter
from weaviate import WeaviateClient

from clients.kp_client import KinopoiskClient
from db_managers import AsyncSessionFactory, MovieManager
from models import MovieObject
from settings import (
    TOP_K_HYBRID,
    TOP_K_FETCH,
    TOP_K_SEARCH,
    TOP_K_SIMILAR,
    WEAVITE_HOST_HTTP,
    WEAVITE_HOST_GRPC,
    WEAVITE_PORT_HTTP,
    WEAVITE_PORT_GRPC,
    MODEL_EMBS,
    CLASS_NAME
)

logger = logging.getLogger(__name__)

def load_vectorstore_weaviate() -> WeaviateClient:
    weaviate_client = WeaviateClient(
        connection_params=ConnectionParams.from_params(
            http_host=WEAVITE_HOST_HTTP,
            http_port=WEAVITE_PORT_HTTP,
            http_secure=False,
            grpc_host=WEAVITE_HOST_GRPC,
            grpc_port=WEAVITE_PORT_GRPC,
            grpc_secure=False,
        )
    )
    return weaviate_client

class MovieWeaviateRecommender:
    def __init__(self,
                 weaviate_client: WeaviateClient,
                 kp_client: KinopoiskClient,
                 openai_client: AsyncOpenAI,
                 model_name=MODEL_EMBS,
                 top_k_hybrid=TOP_K_HYBRID,
                 top_k_fetch=TOP_K_FETCH,
                 top_k_similar=TOP_K_SIMILAR,
                 top_k_search=TOP_K_SEARCH,
                 collection=CLASS_NAME
                 ):
        self.openai_client = openai_client
        self.kp_client = kp_client
        self.top_k_hybrid = top_k_hybrid
        self.top_k_fetch = top_k_fetch
        self.top_k_search = top_k_search
        self.top_k_similar = top_k_similar
        self.model_name = model_name
        self.collection = weaviate_client.collections.get(collection)

    @staticmethod
    def _dynamic_score(item: dict) -> float:
        """
        Вычисляет составной скор фильма на основе рейтингов, голосов, свежести, жанров и страны производства.

        Алгоритм учитывает:
        - логарифмическое количество голосов с IMDb и Кинопоиска;
        - рейтинги IMDb и Кинопоиска;
        - свежесть фильма (снижение за старые фильмы, максимум в 2025 году);
        - штраф за фильмы, которые одновременно являются 'аниме';
        - фильтрацию стендап-комедий (снижение до 0, если жанр 'комедия' и найден текст стендапа);
        - бонус за страны: Франция, Германия, Южная Корея, Испания, Аргентина, Бразилия.

        Возвращает:
            Округлённый скор фильма (float). Фильмы с нулевым или отрицательным скором исключаются.
        """
        rating_kp = item.get("rating_kp") or 0.0
        rating_imdb = item.get("rating_imdb") or 0.0
        votes_kp = item.get("votes_kp") or 0
        votes_imdb = item.get("votes_imdb") or 0
        year = item.get("year") or 2000
        genres = [g.lower() for g in item.get("genres", [])]
        countries = item.get("countries", []) or []
        content = item.get("page_content", "").lower()

        log_votes_imdb = math.log1p(votes_imdb)
        log_votes_kp = math.log1p(votes_kp)

        score = (
            0.2 * log_votes_imdb +
            0.05 * log_votes_kp +
            0.4 * rating_imdb +
            0.4 * rating_kp
        )

        freshness = max(0.0, 1.0 - (2025 - year) / 35)
        score += 1.0 * freshness

        if any(g in genres for g in ["аниме"]):
            score *= 0.85

        if genres == ["комедия"] and any(word in content for word in ["стендап", "stand-up", "выступлен"]):
            return 0.0

        if any(c in countries for c in ["франция", "германия", "южная корея", "испания", "аргентина", "бразилия"]):
            score *= 1.1

        return round(score, 2)

    @staticmethod
    def _skip_due_to_genre_conflict(movie_genres: List[str], selected_genres: List[str]) -> bool:
        """
        Пропускает фильм, если он содержит одновременно 'аниме' и 'мультфильм',
        но пользователь выбрал только 'мультфильм'.
        """
        if "аниме" in movie_genres and "мультфильм" in movie_genres:
            return "аниме" not in selected_genres
        return False

    @classmethod
    def _return_properties(cls) -> List[str]:
        return [
            "kp_id", "year", "genres", "countries", "rating_kp", "rating_imdb",
            "votes_kp", "votes_imdb", "page_content"
        ]

    async def _search_movies(
            self,
            query: Optional[str],
            alpha: float,
            fetch_limit: int,
            result_limit: int,
            filters: Optional[Filter] = None,
            genres: Optional[List[str]] = None,
            exclude_kp_ids: Optional[Set] = None,
    ) -> List[MovieObject]:
        """
        Унифицированный метод поиска фильмов в Weaviate с гибридным (векторным + keyword) или фильтрационным запросом.

        Алгоритм:
        - При наличии `query` генерирует embedding через OpenAI.
        - Выполняет либо гибридный поиск (query + embedding), либо фильтрационный fetch.
        - Применяет фильтрацию по заданным параметрам:
            - exclude_kp_ids — исключает фильмы с указанными ID.
            - genres — исключает фильмы с конфликтующими жанрами ('аниме' + 'мультфильм').
        - Вычисляет `dynamic_score` для каждого фильма.
        - Возвращает отсортированный список фильмов по `dynamic_score` (по убыванию).

        Параметры:
            query (Optional[str]): текстовый запрос пользователя. Если не задан — используется только фильтрация.
            fetch_limit (int): максимальное количество фильмов для описка.
            result_limit (int): максимальное количество возвращаемых фильмов.
            alpha (float): коэффициент смешивания embedding и keyword в гибридном поиске.
            filters: объект фильтров Weaviate (`weaviate.classes.query.Filter`) для фильтрационного запроса.
            genres (Optional[List[str]]): список выбранных жанров пользователя (для дополнительной фильтрации конфликтов).
            exclude_kp_ids (Optional[set]): множество `kp_id`, которые нужно исключить из результатов.

        Возвращает:
            List[MovieObject]: отсортированный список фильмов, соответствующих запросу и фильтрам.
        """
        try:
            if query:
                embedding_response = await self.openai_client.embeddings.create(
                    input=query,
                    model=self.model_name
                )
                embedding = embedding_response.data[0].embedding

                results = self.collection.query.hybrid(
                    vector=embedding,
                    query=query,
                    alpha=alpha,
                    limit=fetch_limit,
                    filters=filters,
                    return_properties=self._return_properties(),
                )
            else:
                results = self.collection.query.fetch_objects(
                    filters=filters,
                    limit=fetch_limit,
                    return_properties=self._return_properties(),
                )

            exclude_set = exclude_kp_ids or set()
            movies = []

            for obj in results.objects:
                props = obj.properties
                kp_id = props.get("kp_id")
                if kp_id in exclude_set:
                    continue

                if genres and self._skip_due_to_genre_conflict(props.get("genres", []), genres):
                    continue

                score = self._dynamic_score(props)
                if score > 0:
                    props["dynamic_score"] = score
                    movies.append(props)

            return sorted(movies, key=lambda x: x["dynamic_score"], reverse=True)[:result_limit]

        except Exception as e:
            logger.warning(f"[MovieRAG] Ошибка в _search_movies: {e}")
            return []

    async def search(self, query: str) -> List[MovieObject]:
        """
        Выполняет гибридный поиск фильмов в Weaviate по заданному текстовому запросу (query).
        """
        return await self._search_movies(
            query=query,
            alpha=0.3,
            fetch_limit=self.top_k_search,
            result_limit=10,
        )

    async def recommend(
        self,
        query: str = None,
        genres: List[str] = None,
        start_year: int = 1900,
        end_year: int = 2025,
        rating_kp: float = 0.0,
        rating_imdb: float = 0.0,
        exclude_kp_ids: Optional[Set[int]] = None
    ) -> List[MovieObject]:
        """
        Рекомендует фильмы на основе гибридного (векторного + keyword) или обычного фильтрационного поиска,
        с учётом жанров, годов, рейтингов и исключённых фильмов. Возвращает отсортированные результаты
        по кастомному скору (_dynamic_score), с дополнительной фильтрацией по конфликту жанров.
        """
        filters = Filter.by_property("year").greater_than(start_year) & \
                  Filter.by_property("year").less_than(end_year) & \
                  Filter.by_property("rating_kp").greater_than(rating_kp) & \
                  Filter.by_property("rating_imdb").greater_than(rating_imdb)

        if genres is not None:
            filters = filters & Filter.by_property("genres").contains_all(genres)

        return await self._search_movies(
            query=query,
            alpha=0.7,
            fetch_limit=self.top_k_hybrid if query else self.top_k_fetch,
            result_limit=100,
            filters=filters,
            genres=genres,
            exclude_kp_ids=exclude_kp_ids
        )

    def recommend_similar(
            self,
            source_kp_id: int,
            penalty_weight: float = 0.15,
            exclude_kp_ids: Optional[Set[int]] = None,
    ) -> List[MovieObject]:
        """
        Ищет фильмы, похожие на заданный по `kp_id`, с переранжировкой по adjusted_distance.

        Алгоритм:
        - Находит UUID и жанры объекта по `kp_id`.
        - Выполняет near_object-поиск ближайших фильмов.
        - Вычисляет dynamic_score.
        - Переранжирует по формуле: distance * (1 + penalty_weight * log1p(10 - dynamic_score)).

        Параметры:
            kp_id (int): идентификатор фильма, для которого ищутся похожие.
            penalty_weight (float): вес штрафа за низкий score.

        Возвращает:
            List[MovieObject]: топ `limit` переранжированных фильмов.
        """
        try:
            result = self.collection.query.fetch_objects(
                filters=Filter.by_property("kp_id").equal(source_kp_id),
                limit=1
            )

            if not result.objects:
                return []

            source_obj = result.objects[0]
            source_uuid = source_obj.uuid
            source_genres = source_obj.properties.get("genres", [])

            response = self.collection.query.near_object(
                near_object=source_uuid,
                limit=self.top_k_similar,
                return_metadata=["distance"],
                return_properties=self._return_properties()
            )

            exclude_set = exclude_kp_ids or set()
            movies = []

            for obj in response.objects:
                props = obj.properties
                obj_kp_id = props.get("kp_id")
                if obj_kp_id == source_kp_id or obj_kp_id in exclude_set:
                    continue

                movie_genres = props.get("genres", [])
                if self._skip_due_to_genre_conflict(movie_genres, source_genres):
                    continue

                dynamic_score = self._dynamic_score(props)
                if dynamic_score <= 0:
                    continue

                distance = obj.metadata.distance
                adjusted_distance = distance * (1 + penalty_weight * math.log1p(10 - dynamic_score))

                props.update({"adjusted_distance": adjusted_distance})
                movies.append(props)

            return sorted(movies, key=lambda x: x["adjusted_distance"])[:100]

        except Exception as e:
            logger.warning(f"[MovieRAG] Ошибка в recommend_reranked_by_kp_id: {e}")
            return []

    @staticmethod
    async def _get_user_excluded_kp_ids(
            user_id,
            movie_manager: MovieManager,
            platform: str = "telegram"
    ) -> Set[int]:
        skipped = await movie_manager.get_skipped(user_id, platform=platform)
        favorites = await movie_manager.get_favorites(user_id, platform=platform)
        return set(skipped + favorites)

    async def _get_or_fetch_movie(
            self,
            kp_id: int,
            session: AsyncSession,
            movie_manager: MovieManager
    ) -> Optional[dict]:
        """
        Получает фильм по kp_id: сначала из БД, при отсутствии — из Kinopoisk API.
        Возвращает сериализованный словарь, либо None при ошибке.
        """
        try:
            movie_response = await asyncio.wait_for(
                movie_manager.get_by_kp_id(kp_id=kp_id), timeout=5
            )
            movie = movie_response.model_dump()
            movie["poster_url"] = movie.get("poster_url")
            movie["movie_id"] = movie.get("movie_id")
            return movie
        except (HTTPException, asyncio.TimeoutError):
            try:
                movie_details = await asyncio.wait_for(
                    self.kp_client.get_by_kp_id(kp_id=kp_id), timeout=5
                )
                if not movie_details:
                    return None
                await movie_manager.insert_movies([movie_details])
                await session.commit()
                movie = movie_details.model_dump()
                movie["poster_url"] = movie_details.google_cloud_url
                movie["movie_id"] = movie_details.kp_id
                return movie
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Таймаут kp_id={kp_id}")
                return None

    async def movie_generator(
            self,
            user_id,
            platform: str = "telegram",
            source_kp_id: int = None,
            query: str = None,
            movie_name: str = None,
            genres: Optional[List[str]] = None,
            start_year: int = 1900,
            end_year: int = 2025,
            rating_kp: float = 5.0,
            rating_imdb: float = 5.0,
    ) -> AsyncGenerator[dict, None]:
        """
        Асинхронный генератор фильмов, отбираемых с учётом фильтров, истории пользователя и Weaviate/Кинопоиск.

        Алгоритм:
        - Если задан `movie_name`, выполняется поиск по названию (через `self.search`).
        - Если задан `source_kp_id`, выполняется поиск похожих на фильм с source_kp_id (через `self.recommend_similar`).
        - Иначе используется метод `recommend`, исключая фильмы из пропущенных и избранных пользователя.

        Параметры:
            user_id: ID пользователя (int для Telegram) или device_id (str для iOS)
            platform: 'telegram' or 'ios'
            source_kp_id (int): ID фильма, к которому нужно подобрать похожие
            query (str, optional): Текстовый запрос (например, атмосфера или описание).
            movie_name (str, optional): Точное имя фильма для поиска (приоритетный путь).
            genres (List[str], optional): Список жанров фильмов.
            start_year (int): Минимальный год выпуска.
            end_year (int): Максимальный год выпуска.
            rating_kp (float): Минимальный рейтинг на Кинопоиске.
            rating_imdb (float): Минимальный рейтинг на IMDb.

        Возвращает:
            Асинхронный генератор объектов фильмов (dict), готовых к отправке в клиент.
        """
        if movie_name and source_kp_id:
            raise ValueError("Нельзя одновременно передавать movie_name и source_kp_id.")

        async with AsyncSessionFactory() as session:
            movie_manager = MovieManager(session)

            exclude_set: set[int] = set()
            if movie_name is None:
                exclude_set = await self._get_user_excluded_kp_ids(
                    user_id=user_id, 
                    movie_manager=movie_manager,
                    platform=platform
                )

            if movie_name is not None:
                movies = await self.search(query=movie_name)
            elif source_kp_id is not None:
                movies=self.recommend_similar(
                    source_kp_id=source_kp_id,
                    exclude_kp_ids=exclude_set
                )
            else:
                movies = await self.recommend(
                    query=query,
                    genres=genres,
                    start_year=start_year,
                    end_year=end_year,
                    rating_kp=rating_kp,
                    rating_imdb=rating_imdb,
                    exclude_kp_ids=exclude_set
                )

            for movie in movies:
                kp_id = movie.get("kp_id")
                if kp_id and (result := await self._get_or_fetch_movie(kp_id, session, movie_manager)):
                    yield result