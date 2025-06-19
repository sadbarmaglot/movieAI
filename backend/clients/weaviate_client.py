import json
import math
import logging
import traceback
import time
import asyncio

from openai import OpenAI
from weaviate import WeaviateClient
from weaviate.classes.query import Filter
from weaviate.connect import ConnectionParams
from typing import Optional, List, TypedDict

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from clients.kp_client import KinopoiskClient
from db_managers import AsyncSessionFactory, MovieManager
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

HEARTBEAT_INTERVAL = 2.0

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

        rating_kp = item.get("rating_kp", 0.0)
        rating_imdb = item.get("rating_imdb", 0.0)
        votes_kp = item.get("votes_kp", 0)
        votes_imdb = item.get("votes_imdb", 0)
        year = item.get("year", 2000)
        genres = [g.lower() for g in item.get("genres", [])]
        countries = item.get("countries", []) or []
        # countries = [c.strip().lower() for c in countries.split(",") if c]
        content = item.get("page_content", "").lower()

        # Логарифмическая сглаженность
        log_votes_imdb = math.log1p(votes_imdb)
        log_votes_kp = math.log1p(votes_kp)

        # Основной скор
        score = (
            0.2 * log_votes_imdb +
            0.05 * log_votes_kp +
            0.4 * rating_imdb +
            0.4 * rating_kp
        )

        # Бонус за свежесть
        freshness = max(0.0, 1.0 - (2025 - year) / 35)
        score += 1.0 * freshness

        # Штраф за аниме и мультфильмы
        if any(g in genres for g in ["аниме", "мультфильм"]):
            score *= 0.85

        # Штраф за стендап/спешал
        if genres == ["комедия"] and any(word in content for word in ["стендап", "stand-up", "выступлен"]):
            return 0.0  # вообще исключаем

        # Бонус за страны (европа, латам, корея)
        if any(c in countries for c in ["франция", "германия", "южная корея", "испания", "аргентина", "бразилия"]):
            score *= 1.1

        return round(score, 2)

    def search(self, query: str):
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
                return_properties=["kp_id", "popularity_score"]
            )

            objects = [
                obj.properties for obj in results.objects
                if obj.properties.get("popularity_score", 0) >= 5
            ]

            reranked = sorted(objects, key=lambda x: x["popularity_score"], reverse=True)

            return reranked[:10]

        except Exception as e:
            logger.warning(f"[MovieSearch] Ошибка запроса к Weaviate: {e}")
            return []

    def recommend(self,
                  query: str = None,
                  genres: List[str] = None,
                  start_year: int = 1900,
                  end_year: int = 2025,
                  rating_kp: float = 0.0,
                  rating_imdb: float = 0.0
                  ) -> List[MovieObject]:

        filters = Filter.by_property("year").greater_than(start_year) & \
                  Filter.by_property("year").less_than(end_year) & \
                  Filter.by_property("rating_kp").greater_than(rating_kp) & \
                  Filter.by_property("rating_imdb").greater_than(rating_imdb)

        if genres:
            filters = filters & Filter.by_property("genres").contains_any(genres)

        try:
            if query:
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
            for obj in results.objects:
                score = self._dynamic_score(obj.properties)
                if score > 0:
                    obj.properties["dynamic_score"] = score
                    objects.append(obj.properties)

            movies: List[MovieObject] = sorted(objects, key=lambda x: x["dynamic_score"], reverse=True)
            return movies

        except Exception as e:
            logger.warning(f"[MovieRAG] Ошибка запроса к Weaviate: {e}")
            return []

    async def stream_movies_from_vector_search_old(
            self,
            user_id: int,
            query: str = None,
            genres: Optional[List[str]] = None,
            start_year: int = 1900,
            end_year: int = 2025,
            rating_kp: float = 5.0,
            rating_imdb: float = 5.0,
            exclude: Optional[List[int]] = None,
            favorites: Optional[List[int]] = None,
            max_results: int = 50
    ) -> StreamingResponse:

        movies = self.recommend(
            query=query,
            genres=genres,
            start_year=start_year,
            end_year=end_year,
            rating_kp=rating_kp,
            rating_imdb=rating_imdb,
        )

        async def stream_generator():
            queue = asyncio.Queue()

            async def producer():
                async with AsyncSessionFactory() as session:
                    async with session.begin():
                        movie_manager = MovieManager(session)

                        for movie in movies:
                            kp_id = movie.get("kp_id")
                            if not kp_id:
                                continue

                            start_total = time.monotonic()

                            try:
                                try:
                                    movie_response = await movie_manager.get_by_kp_id(kp_id=kp_id)
                                    movie = movie_response.model_dump()
                                    movie["poster_url"] = movie.get("poster_url")
                                    movie["movie_id"] = movie.get("movie_id")

                                except HTTPException:
                                    logger.info(f"📡 kp_id={kp_id} не найден в БД, иду в Кинопоиск...")

                                    start_kp = time.monotonic()
                                    movie_details = await self.kp_client.get_by_kp_id(kp_id=kp_id)
                                    if not movie_details:
                                        continue
                                    logger.info(f"📥 Получен с Кинопоиска за {time.monotonic() - start_kp:.3f}s")

                                    await movie_manager.insert_movies([movie_details])

                                    movie = movie_details.model_dump()
                                    movie["poster_url"] = movie_details.google_cloud_url
                                    movie["movie_id"] = movie_details.kp_id

                                await queue.put(json.dumps(movie, ensure_ascii=False) + "\n")

                            except Exception as e:
                                logger.warning(f"❌ Ошибка в стриме kp_id={kp_id}: {e}\n{traceback.format_exc()}")

                        logger.info(f"✅ Полный цикл kp_id={kp_id} занял {time.monotonic() - start_total:.3f}s\n")
                        await queue.put(None)  # сигнал завершения

            async def heartbeat():
                while True:
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
                    await queue.put(" \n")

            producer_task = asyncio.create_task(producer())
            heartbeat_task = asyncio.create_task(heartbeat())

            while True:
                chunk = await queue.get()
                if chunk is None:
                    heartbeat_task.cancel()
                    producer_task.cancel()
                    break
                yield chunk

        return StreamingResponse(stream_generator(), media_type="application/json")

    async def stream_movies_from_vector_search(
            self,
            user_id: int,
            query: str = None,
            genres: Optional[List[str]] = None,
            start_year: int = 1900,
            end_year: int = 2025,
            rating_kp: float = 5.0,
            rating_imdb: float = 5.0,
            exclude: Optional[List[int]] = None,
            favorites: Optional[List[int]] = None,
            max_results: int = 50
    ) -> StreamingResponse:

        movies = self.recommend(
            query=query,
            genres=genres,
            start_year=start_year,
            end_year=end_year,
            rating_kp=rating_kp,
            rating_imdb=rating_imdb,
        )

        ping_interval = 5

        async def stream_generator():
            try:
                async with AsyncSessionFactory() as session:
                    movie_manager = MovieManager(session)
                    last_yield_time = time.monotonic()

                    for movie in movies:
                        now = time.monotonic()

                        if now - last_yield_time > ping_interval:
                            yield "\n"
                            last_yield_time = now

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
                            yield " \n"
                            try:
                                movie_details = await asyncio.wait_for(
                                    self.kp_client.get_by_kp_id(kp_id=kp_id), timeout=5
                                )
                                if not movie_details:
                                    continue
                                await movie_manager.insert_movies([movie_details])
                                movie = movie_details.model_dump()
                                movie["poster_url"] = movie_details.google_cloud_url
                                movie["movie_id"] = movie_details.kp_id
                            except asyncio.TimeoutError:
                                logger.warning(f"⏱️ Таймаут при получении или вставке kp_id={kp_id}")
                                continue

                        yield json.dumps(movie, ensure_ascii=False) + "\n"
                        last_yield_time = time.monotonic()
                        
            except Exception as e:
                logger.warning(f"❌ Ошибка в stream_generator: {e}")
                yield "\n"
            finally:
                yield "\n"

        return StreamingResponse(stream_generator(), media_type="text/plain")