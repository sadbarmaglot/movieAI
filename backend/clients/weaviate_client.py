import math
import logging

from typing import Optional, List, Set, AsyncGenerator
from openai import AsyncOpenAI
from weaviate.connect import ConnectionParams
from weaviate.classes.query import Filter
from weaviate import WeaviateClient

from clients.kp_client import KinopoiskClient
from db_managers import AsyncSessionFactory, MovieManager
from settings import (
    TOP_K_HYBRID,
    TOP_K_FETCH,
    TOP_K_SEARCH,
    TOP_K_SIMILAR,
    WEAVIATE_HOST_HTTP,
    WEAVIATE_HOST_GRPC,
    WEAVIATE_PORT_HTTP,
    WEAVIATE_PORT_GRPC,
    MODEL_EMBS,
    CLASS_NAME,
    DEFAULT_LOCALE,
)

logger = logging.getLogger(__name__)

def load_vectorstore_weaviate() -> WeaviateClient:
    weaviate_client = WeaviateClient(
        connection_params=ConnectionParams.from_params(
            http_host=WEAVIATE_HOST_HTTP,
            http_port=WEAVIATE_PORT_HTTP,
            http_secure=False,
            grpc_host=WEAVIATE_HOST_GRPC,
            grpc_port=WEAVIATE_PORT_GRPC,
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
        """
        Возвращает полный список свойств для запроса из Movie_v2.
        Запрашиваем все поля (и русские, и английские) для упрощения логики.
        """
        return [
            "kp_id", "tmdb_id", "imdb_id", "year", "movieLength",
            "rating_kp", "rating_imdb", "popularity_score",
            "kp_file_path", "kp_background_color",
            "tmdb_file_path", "tmdb_background_color",
            "cast", "directors", "keywords", "page_content",
            # Локализованные поля (русские)
            "name", "description", "genres", "countries",
            # Локализованные поля (английские)
            "title", "overview", "genres_tmdb", "origin_country"
        ]

    @staticmethod
    def _weaviate_to_movie_dict(props: dict) -> dict:
        """
        Преобразует данные из Weaviate в унифицированный формат.
        Возвращает все поля как есть, без разделения по локализации.
        """
        return {
            "kp_id": props.get("kp_id"),
            "tmdb_id": props.get("tmdb_id"),
            "imdb_id": props.get("imdb_id"),
            "year": props.get("year"),
            "movieLength": props.get("movieLength"),
            "rating_kp": props.get("rating_kp") or 0.0,
            "rating_imdb": props.get("rating_imdb") or 0.0,
            "popularity_score": props.get("popularity_score"),
            "cast": props.get("cast", []),
            "directors": props.get("directors", []),
            "keywords": props.get("keywords", []),
            "page_content": props.get("page_content", ""),
            # Локализованные поля (русские)
            "name": props.get("name", ""),
            "description": props.get("description", ""),
            "genres": props.get("genres", []),
            "countries": props.get("countries", []),
            # Локализованные поля (английские)
            "title": props.get("title", ""),
            "overview": props.get("overview", ""),
            "genres_tmdb": props.get("genres_tmdb", []),
            "origin_country": props.get("origin_country", []),
            # Постеры и цвета фона
            "kp_file_path": props.get("kp_file_path", ""),
            "kp_background_color": props.get("kp_background_color"),
            "tmdb_file_path": props.get("tmdb_file_path", ""),
            "tmdb_background_color": props.get("tmdb_background_color"),
        }

    async def _search_movies(
            self,
            query: Optional[str],
            alpha: float,
            fetch_limit: int,
            result_limit: int,
            filters: Optional[Filter] = None,
            genres: Optional[List[str]] = None,
            exclude_kp_ids: Optional[Set] = None,
    ) -> List[dict]:
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
            List[dict]: отсортированный список фильмов, соответствующих запросу и фильтрам.
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
            excluded_count = 0
            genre_conflict_count = 0

            for obj in results.objects:
                props = obj.properties
                kp_id = props.get("kp_id")
                if kp_id in exclude_set:
                    excluded_count += 1
                    logger.debug(
                        f"[WeaviateRecommender] _search_movies: фильм kp_id={kp_id} исключен "
                        f"(находится в exclude_set)"
                    )
                    continue

                movie_dict = self._weaviate_to_movie_dict(props)
                
                if genres:
                    movie_genres = movie_dict.get("genres", [])
                    if self._skip_due_to_genre_conflict(movie_genres, genres):
                        genre_conflict_count += 1
                        logger.debug(
                            f"[WeaviateRecommender] _search_movies: фильм kp_id={kp_id} исключен "
                            f"из-за конфликта жанров: {movie_genres} vs {genres}"
                        )
                        continue

                movies.append(movie_dict)
            
            if len(results.objects) == 0:
                logger.warning(
                    f"[WeaviateRecommender] _search_movies: Weaviate вернул 0 объектов! "
                    f"query='{query[:100] if query else 'None'}...', "
                    f"filters применены, fetch_limit={fetch_limit}"
                )
            
            logger.info(
                f"[WeaviateRecommender] _search_movies: обработано {len(results.objects)} объектов, "
                f"исключено по exclude_set: {excluded_count}, исключено по жанрам: {genre_conflict_count}, "
                f"осталось: {len(movies)}, вернется: {min(len(movies), result_limit)}"
            )
            
            return sorted(movies, key=lambda x: x.get("popularity_score") or 0.0, reverse=True)[:result_limit]

        except Exception as e:
            logger.warning(f"[MovieRAG] Ошибка в _search_movies: {e}")
            return []

    async def search(self, query: str) -> List[dict]:
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
        exclude_kp_ids: Optional[Set[int]] = None,
        locale: str = DEFAULT_LOCALE,
    ) -> List[dict]:
        """
        Рекомендует фильмы на основе гибридного (векторного + keyword) или обычного фильтрационного поиска,
        с учётом жанров, годов, рейтингов и исключённых фильмов. Возвращает отсортированные результаты
        по кастомному скору (popularity_score), с дополнительной фильтрацией по конфликту жанров.
        
        Использует alpha=0.95 для приоритета векторного поиска над keyword поиском, что улучшает
        семантический поиск для запросов типа "фильмы на рождество" и снижает влияние точных совпадений.
        """
        exclude_set = exclude_kp_ids or set()
        logger.info(
            f"[WeaviateRecommender] recommend вызван: query='{query}', genres={genres}, "
            f"years={start_year}-{end_year}, exclude_kp_ids={len(exclude_set)} фильмов "
            f"{list(exclude_set)[:20]}{'...' if len(exclude_set) > 20 else ''}, locale={locale}"
        )
        
        filters = Filter.by_property("year").greater_than(start_year) & \
                  Filter.by_property("year").less_than(end_year) & \
                  Filter.by_property("rating_kp").greater_than(rating_kp) & \
                  Filter.by_property("rating_imdb").greater_than(rating_imdb)

        if genres is not None and len(genres) > 0:
            logger.info(
                f"[WeaviateRecommender] Получены genres: {genres}, type: {type(genres)}, "
                f"locale={locale}"
            )
            if locale == "en":
                genre_filter = Filter.by_property("genres_tmdb").contains_any(genres)
                logger.info(
                    f"[WeaviateRecommender] Применяем фильтр по жанрам для locale=en: "
                    f"genres={genres}, фильтр: genres_tmdb.contains_any({genres})"
                )
                filters = filters & genre_filter
            else:
                genre_filter = Filter.by_property("genres").contains_any(genres)
                logger.info(
                    f"[WeaviateRecommender] Применяем фильтр по жанрам для locale=ru: "
                    f"genres={genres}, фильтр: genres.contains_any({genres})"
                )
                filters = filters & genre_filter
        else:
            logger.debug(f"[WeaviateRecommender] Жанры не указаны, фильтр по жанрам не применяется")

        logger.debug(
            f"[WeaviateRecommender] Итоговые фильтры: year>{start_year} & year<{end_year} & "
            f"rating_kp>{rating_kp} & rating_imdb>{rating_imdb}"
            + (f" & genres filter" if genres else "")
        )

        results = await self._search_movies(
            query=query,
            alpha=0.95,  # Увеличено с 0.8 для снижения влияния keyword поиска на семантические запросы
            fetch_limit=self.top_k_hybrid if query else self.top_k_fetch,
            result_limit=100,
            filters=filters,
            genres=genres,
            exclude_kp_ids=exclude_kp_ids
        )
        
        result_kp_ids = [m.get("kp_id") for m in results]
        excluded_in_results = [kp_id for kp_id in result_kp_ids if kp_id in exclude_set]
        if excluded_in_results:
            logger.warning(
                f"[WeaviateRecommender] ВНИМАНИЕ: В результатах recommend найдены исключенные фильмы! "
                f"exclude_set содержит {len(exclude_set)} фильмов, но в результатах присутствуют: {excluded_in_results}"
            )
        else:
            logger.info(
                f"[WeaviateRecommender] recommend вернул {len(results)} фильмов, "
                f"все исключены корректно. KP IDs результатов: {result_kp_ids[:20]}{'...' if len(result_kp_ids) > 20 else ''}"
            )
        
        return results

    async def get_movie_by_kp_id(self, kp_id: int) -> Optional[dict]:
        """
        Получает фильм из Weaviate по kp_id.
        
        Args:
            kp_id: ID фильма на Кинопоиске
            
        Returns:
            dict: данные фильма в формате из _weaviate_to_movie_dict или None если не найден
        """
        try:
            result = self.collection.query.fetch_objects(
                filters=Filter.by_property("kp_id").equal(kp_id),
                limit=1,
                return_properties=self._return_properties()
            )
            
            if not result.objects:
                logger.warning(f"[get_movie_by_kp_id] Фильм kp_id={kp_id} не найден в Weaviate")
                return None
            
            props = result.objects[0].properties
            return self._weaviate_to_movie_dict(props)
        except Exception as e:
            logger.warning(f"[get_movie_by_kp_id] Ошибка при получении фильма kp_id={kp_id}: {e}")
            return None

    async def recommend_similar(
            self,
            source_kp_id: int,
            penalty_weight: float = 0.15,
            exclude_kp_ids: Optional[Set[int]] = None,
    ) -> List[dict]:
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
            List[dict]: топ `limit` переранжированных фильмов.
        """
        try:
            result = self.collection.query.fetch_objects(
                filters=Filter.by_property("kp_id").equal(source_kp_id),
                limit=1,
                return_properties=self._return_properties()
            )

            if not result.objects:
                return []

            source_obj = result.objects[0]
            source_uuid = source_obj.uuid
            source_props = source_obj.properties
            
            source_genres = source_props.get("genres", [])

            response = self.collection.query.near_object(
                near_object=source_uuid,
                limit=self.top_k_similar,
                return_metadata=["distance"],
                return_properties=self._return_properties()
            )

            exclude_set = exclude_kp_ids or set()
            movies = []
            excluded_count = 0
            genre_conflict_count = 0
            low_score_count = 0

            logger.info(
                f"[WeaviateRecommender] recommend_similar: source_kp_id={source_kp_id}, "
                f"exclude_kp_ids={len(exclude_set)} фильмов, "
                f"получено {len(response.objects)} похожих фильмов"
            )

            for obj in response.objects:
                props = obj.properties
                obj_kp_id = props.get("kp_id")
                if obj_kp_id == source_kp_id or obj_kp_id in exclude_set:
                    excluded_count += 1
                    logger.debug(
                        f"[WeaviateRecommender] recommend_similar: фильм kp_id={obj_kp_id} исключен "
                        f"(source_kp_id={source_kp_id} или в exclude_set)"
                    )
                    continue

                movie_dict = self._weaviate_to_movie_dict(props)
                movie_genres = movie_dict.get("genres", [])
                
                if self._skip_due_to_genre_conflict(movie_genres, source_genres):
                    genre_conflict_count += 1
                    logger.debug(
                        f"[WeaviateRecommender] recommend_similar: фильм kp_id={obj_kp_id} исключен "
                        f"из-за конфликта жанров"
                    )
                    continue

                dynamic_score = movie_dict.get("popularity_score") or 0.0
                if dynamic_score <= 0:
                    low_score_count += 1
                    continue

                distance = obj.metadata.distance
                adjusted_distance = distance * (1 + penalty_weight * math.log1p(10 - dynamic_score))

                movie_dict["adjusted_distance"] = adjusted_distance
                movies.append(movie_dict)

            result_kp_ids = [m.get("kp_id") for m in movies]
            excluded_in_results = [kp_id for kp_id in result_kp_ids if kp_id in exclude_set]
            if excluded_in_results:
                logger.warning(
                    f"[WeaviateRecommender] ВНИМАНИЕ: В результатах recommend_similar найдены исключенные фильмы! "
                    f"exclude_set содержит {len(exclude_set)} фильмов, но в результатах присутствуют: {excluded_in_results}"
                )
            
            logger.info(
                f"[WeaviateRecommender] recommend_similar: исключено по exclude_set/source: {excluded_count}, "
                f"исключено по жанрам: {genre_conflict_count}, исключено по score: {low_score_count}, "
                f"осталось: {len(movies)}, вернется: {min(len(movies), 100)}"
            )

            return sorted(movies, key=lambda x: x["adjusted_distance"])[:100]

        except Exception as e:
            logger.warning(f"[MovieRAG] Ошибка в recommend_similar: {e}")
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
            locale: str = DEFAULT_LOCALE,
    ) -> AsyncGenerator[dict, None]:
        """
        Асинхронный генератор фильмов, отбираемых с учётом фильтров, истории пользователя и Weaviate.

        Алгоритм:
        - Если задан `movie_name`, выполняется поиск по названию (через `self.search`).
        - Если задан `source_kp_id`, выполняется поиск похожих на фильм с source_kp_id (через `self.recommend_similar`).
        - Иначе используется метод `recommend`, исключая фильмы из пропущенных и избранных пользователя.
        - Все данные берутся из Weaviate (Movie_v2), без обращения к внешним API.

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
                movies = await self.recommend_similar(
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
                    exclude_kp_ids=exclude_set,
                    locale=locale
                )

            for movie in movies:
                if locale == "en":
                    genres = movie.get("genres_tmdb", [])
                    countries = movie.get("origin_country", [])
                    
                    yield {
                        "movie_id": movie.get("kp_id"),
                        "title": movie.get("title"),
                        "overview": movie.get("overview"),
                        "poster_url": movie.get("tmdb_file_path"),
                        "year": movie.get("year"),
                        "rating_kp": movie.get("rating_kp"),
                        "rating_imdb": movie.get("rating_imdb"),
                        "movie_length": movie.get("movieLength"),
                        "genres": [{"name": g} for g in genres] if genres else [],
                        "countries": [{"name": c} for c in countries] if countries else [],
                        "background_color": movie.get("tmdb_background_color")
                    }
                else:  # ru
                    genres = movie.get("genres", [])
                    countries = movie.get("countries", [])
                    
                    yield {
                        "movie_id": movie.get("kp_id"),
                        "name": movie.get("name"),  # русское название
                        "title": movie.get("title", ""),  # английское название
                        "overview": movie.get("description"),
                        "poster_url": movie.get("kp_file_path"),
                        "year": movie.get("year"),
                        "rating_kp": movie.get("rating_kp"),
                        "rating_imdb": movie.get("rating_imdb"),
                        "movie_length": movie.get("movieLength"),
                        "genres": [{"name": g} for g in genres] if genres else [],
                        "countries": [{"name": c} for c in countries] if countries else [],
                        "background_color": movie.get("kp_background_color")
                    }