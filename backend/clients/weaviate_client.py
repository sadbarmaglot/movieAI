import math
import logging
import asyncio

from openai import OpenAI
from weaviate import WeaviateClient
from weaviate.classes.query import Filter
from weaviate.connect import ConnectionParams
from typing import Optional, List, TypedDict
from fastapi import HTTPException

from clients.kp_client import KinopoiskClient
from db_managers import AsyncSessionFactory, MovieManager, FavoriteManager
from settings import (
    TOP_K,
    TOP_K_SEARCH,
    WEAVITE_HOST_HTTP,
    WEAVITE_HOST_GRPC,
    WEAVITE_PORT_HTTP,
    WEAVITE_PORT_GRPC,
    MODEL_EMBS,
    CLASS_NAME
)

logger = logging.getLogger(__name__)

class MovieObject(TypedDict):
    kp_id: int
    title_ru: str
    year: int
    genres: Optional[List[str]]
    rating_kp: float
    rating_imdb: float
    page_content: str

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
                 openai_client: OpenAI,
                 model_name=MODEL_EMBS,
                 top_k=TOP_K,
                 top_k_search=TOP_K_SEARCH,
                 collection=CLASS_NAME
                 ):
        self.openai_client = openai_client
        self.kp_client = kp_client
        self.top_k = top_k
        self.top_k_search = top_k_search
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

    def search(self, query: str) -> List[MovieObject]:
        """
        Выполняет гибридный поиск фильмов в Weaviate по заданному текстовому запросу (query).

        Алгоритм:
        - Генерирует embedding из текста с помощью OpenAI.
        - Выполняет hybrid-поиск по коллекции (комбинация embedding + keyword).
        - Оценивает каждый результат с помощью `_dynamic_score`.
        - Возвращает топ-10 фильмов с положительным скором, отсортированных по убыванию этого значения.

        Параметры:
            query (str): текстовый запрос пользователя (например, название желаемого фильма или ключевые слова).

        Возвращает:
            List[MovieObject]: список из до 10 подходящих фильмов.

        Примечание:
            Результаты фильтруются по смысловой релевантности и бизнес-логике через динамический скоринг.
        """
        embedding = self.openai_client.embeddings.create(
            input=query,
            model=self.model_name
        ).data[0].embedding

        try:
            results = self.collection.query.hybrid(
                vector=embedding,
                query=query,
                alpha=0.3,
                limit=self.top_k_search,
                return_properties=[
                    "kp_id", "year", "genres", "countries",
                    "rating_kp", "rating_imdb", "votes_kp", "votes_imdb", "page_content"
                ]
            )

            objects = []
            for obj in results.objects:
                score = self._dynamic_score(obj.properties)
                if score > 0:
                    obj.properties["dynamic_score"] = score
                    objects.append(obj.properties)

            movies: List[MovieObject] = sorted(objects, key=lambda x: x["dynamic_score"], reverse=True)[:10]
            return movies

        except Exception as e:
            logger.warning(f"[MovieRAG] Ошибка запроса к Weaviate: {e}")
            return []

    @staticmethod
    def _skip_due_to_genre_conflict(movie_genres: List[str], selected_genres: List[str]) -> bool:
        """
        Пропускает фильм, если он содержит и 'аниме', и 'мультфильм', а пользователь выбрал только один из них.
        """
        if "аниме" in movie_genres and "мультфильм" in movie_genres:
            return not ("аниме" in selected_genres and "мультфильм" in selected_genres)
        return False

    def recommend(self,
                  query: str = None,
                  genres: List[str] = None,
                  start_year: int = 1900,
                  end_year: int = 2025,
                  rating_kp: float = 0.0,
                  rating_imdb: float = 0.0,
                  exclude_kp_ids: Optional[List[int]] = None
                  ) -> List[MovieObject]:
        """
        Выполняет векторный и/или фильтрационный поиск фильмов с учётом параметров пользователя и возвращает
        отсортированный список рекомендаций по вычисленному скору.

        Параметры:
            query (str, optional): текстовый запрос для генерации эмбеддинга (если задан — используется гибридный поиск).
            genres (List[str], optional): жанры, которые пользователь хочет видеть.
            start_year (int): начальный год выпуска фильма.
            end_year (int): конечный год выпуска фильма.
            rating_kp (float): минимальный рейтинг Кинопоиска.
            rating_imdb (float): минимальный рейтинг IMDb.
            exclude_kp_ids (List[int], optional): список фильмов, которые нужно исключить (например, уже просмотренные).

        Возвращает:
            List[MovieObject]: список до 100 фильмов, отсортированных по убыванию dynamic_score.

        Особенности:
        - Если `query` задан, используется гибридный поиск (vector + keyword).
        - Применяются фильтры по году, рейтингу, жанрам и исключённым фильмам.
        - Исключаются фильмы, нарушающие конфликт жанров (например, одновременно "аниме" и "мультфильм", если только не запрошены оба).
        - Каждый фильм получает оценку через `_dynamic_score`, и только положительные результаты возвращаются.
        """
        filters = Filter.by_property("year").greater_than(start_year) & \
                  Filter.by_property("year").less_than(end_year) & \
                  Filter.by_property("rating_kp").greater_than(rating_kp) & \
                  Filter.by_property("rating_imdb").greater_than(rating_imdb)

        if genres is not None:
            filters = filters & Filter.by_property("genres").contains_any(genres)

        try:
            if query is not None:
                embedding = self.openai_client.embeddings.create(
                    input=query,
                    model=self.model_name
                ).data[0].embedding

                results = self.collection.query.hybrid(
                    query=query,
                    vector=embedding,
                    alpha=0.7,
                    limit=self.top_k,
                    filters=filters,
                    return_properties=[
                        "kp_id", "year", "genres", "countries",
                        "rating_kp", "rating_imdb", "votes_kp", "votes_imdb", "page_content"
                    ]
                )
            else:
                results = self.collection.query.fetch_objects(
                    filters=filters,
                    limit=self.top_k,
                    return_properties=[
                        "kp_id", "year", "genres", "countries",
                        "rating_kp", "rating_imdb", "votes_kp", "votes_imdb", "page_content"
                    ],
                )

            objects = []
            exclude_set = set(exclude_kp_ids) if exclude_kp_ids else set()

            for obj in results.objects:

                kp_id = obj.properties.get("kp_id")
                if kp_id in exclude_set:
                    continue

                if genres is not None:
                    movie_genres = obj.properties.get("genres", [])
                    if self._skip_due_to_genre_conflict(movie_genres, genres):
                        continue

                score = self._dynamic_score(obj.properties)
                if score > 0:
                    obj.properties["dynamic_score"] = score
                    objects.append(obj.properties)

            movies: List[MovieObject] = sorted(objects, key=lambda x: x["dynamic_score"], reverse=True)[:100]
            return movies

        except Exception as e:
            logger.warning(f"[MovieRAG] Ошибка запроса к Weaviate: {e}")
            return []

    async def movie_generator(
            self,
            user_id: int,
            query: str = None,
            movie_name: str = None,
            genres: Optional[List[str]] = None,
            start_year: int = 1900,
            end_year: int = 2025,
            rating_kp: float = 5.0,
            rating_imdb: float = 5.0,
    ):
        """
        Асинхронный генератор фильмов, отбираемых с учётом фильтров, истории пользователя и Weaviate/Кинопоиск.

        Алгоритм:
        - Если задан `movie_name`, выполняется поиск по названию (через `self.search`).
        - Иначе используется метод `recommend`, исключая фильмы из пропущенных и избранных пользователя.
        - Для каждого фильма:
            - Пытается получить данные из базы (`MovieManager.get_by_kp_id`).
            - Если нет — запрашивает у Kinopoisk API и сохраняет в базу.
            - Возвращает сериализованный объект фильма (dict с `poster_url` и `movie_id`).

        Параметры:
            user_id (int): ID пользователя Telegram.
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
        async with AsyncSessionFactory() as session:
            movie_manager = MovieManager(session)

            if movie_name is not None:
                movies = self.search(query=movie_name)
            else:
                exclude_list = await movie_manager.get_skipped(user_id=user_id)
                favorite_list = await movie_manager.get_favorites(user_id=user_id)
                exclude_list.extend(favorite_list)
                movies = self.recommend(
                    query=query,
                    genres=genres,
                    start_year=start_year,
                    end_year=end_year,
                    rating_kp=rating_kp,
                    rating_imdb=rating_imdb,
                    exclude_kp_ids=exclude_list
                )

            for movie in movies:
                kp_id = movie.get("kp_id")
                if not kp_id:
                    continue

                try:
                    movie_response = await asyncio.wait_for(
                        movie_manager.get_by_kp_id(kp_id=kp_id), timeout=5
                    )
                    movie = movie_response.model_dump()
                    movie["poster_url"] = movie.get("poster_url")
                    movie["movie_id"] = movie.get("movie_id")
                except (HTTPException, asyncio.TimeoutError):
                    try:
                        movie_details = await asyncio.wait_for(
                            self.kp_client.get_by_kp_id(kp_id=kp_id), timeout=5
                        )
                        if not movie_details:
                            continue
                        await movie_manager.insert_movies([movie_details])
                        await session.commit()
                        movie = movie_details.model_dump()
                        movie["poster_url"] = movie_details.google_cloud_url
                        movie["movie_id"] = movie_details.kp_id
                    except asyncio.TimeoutError:
                        logger.warning(f"⏱️ Таймаут kp_id={kp_id}")
                        continue

                yield movie
