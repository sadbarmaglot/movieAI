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

        rating_kp = item.get("rating_kp", 0.0)
        rating_imdb = item.get("rating_imdb", 0.0)
        votes_kp = item.get("votes_kp", 0)
        votes_imdb = item.get("votes_imdb", 0)
        year = item.get("year", 2000)
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

        if any(g in genres for g in ["аниме", "мультфильм"]):
            score *= 0.85

        if genres == ["комедия"] and any(word in content for word in ["стендап", "stand-up", "выступлен"]):
            return 0.0

        if any(c in countries for c in ["франция", "германия", "южная корея", "испания", "аргентина", "бразилия"]):
            score *= 1.1

        return round(score, 2)

    def search(self, query: str) -> List[MovieObject]:
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


    def recommend(self,
                  query: str = None,
                  genres: List[str] = None,
                  start_year: int = 1900,
                  end_year: int = 2025,
                  rating_kp: float = 0.0,
                  rating_imdb: float = 0.0,
                  exclude_kp_ids: Optional[List[int]] = None
                  ) -> List[MovieObject]:

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
