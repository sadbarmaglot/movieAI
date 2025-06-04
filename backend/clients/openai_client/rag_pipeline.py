import json
import math
import logging

from openai import OpenAI
from openai import OpenAIError
from langchain_core.runnables import RunnableMap
from langchain.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from weaviate import WeaviateClient
from weaviate.classes.query import Filter
from weaviate.connect import ConnectionParams

from settings import (
    MODEL_MOVIES,
    TOP_K,
    INDEX_PATH,
    WEAVITE_HOST,
    WEAVITE_HTTP_PORT,
    WEAVITE_GRPC_PORT,
    MODEL_EMBS,
    CLASS_NAME
)

logger = logging.getLogger(__name__)

def sanitize_metadata(meta: dict) -> dict:
    return {
        k: (v if not isinstance(v, float) or math.isfinite(v) else None)
        for k, v in meta.items()
    }


def load_vectorstore_faiss() -> FAISS:
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.load_local(
        folder_path=INDEX_PATH,
        embeddings=embeddings,
        allow_dangerous_deserialization=True
    )
    return vectorstore


def load_vectorstore_weaviate() -> WeaviateClient:
    weaviate_client = WeaviateClient(
        connection_params=ConnectionParams.from_params(
            http_host=WEAVITE_HOST,
            http_port=WEAVITE_HTTP_PORT,
            http_secure=False,
            grpc_host=WEAVITE_HOST,
            grpc_port=WEAVITE_GRPC_PORT,
            grpc_secure=False,
        )
    )

    return weaviate_client

class MovieRAGRecommender:
    def __init__(self, vectorstore: FAISS, model_name=MODEL_MOVIES, k=TOP_K):
        self.vectorstore = vectorstore
        self.k = k
        self.model_name = model_name

        @tool
        def select_top_movies_by_index(indices: list[int]) -> list[int]:
            """Выбирает лучшие фильмы по индексам."""
            return indices

        self.llm = ChatOpenAI(model=self.model_name).bind_tools(
            tools=[select_top_movies_by_index],
            function_call={"name": "select_top_movies_by_index"}
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "Ты — рекомендательная система, которая отбирает лучшие фильмы."),
            (
                "user",
                "Вот список фильмов в формате JSON:\n{context_json}\n\n"
                "Выбери 100 фильмов, которые наиболее подходят под запрос: \"{question}\".\n"
                "Верни их индексы (ключ `index`) с помощью вызова функции select_top_movies_by_index."
            )
        ])

        self.agent = (
            RunnableMap({
                "context_json": lambda x: json.dumps(
                    self._create_context_json(x["docs"]), ensure_ascii=False
                ),
                "question": lambda x: x["question"]
            })
            | self.prompt
            | self.llm
            | JsonOutputFunctionsParser()
        )

    @staticmethod
    def _create_context_json(docs):
        return [
            {
                "index": i,
                "kp_id": d.metadata.get("kp_id"),
                "title": d.metadata.get("title_ru"),
                "year": d.metadata.get("year"),
                "genres": d.metadata.get("genres"),
                "rating_kp": d.metadata.get("rating_kp", "-"),
                "rating_imdb": d.metadata.get("rating_imdb", "-"),
                "description": d.page_content[:400],
            }
            for i, d in enumerate(docs)
        ]

    def recommend(self, question: str):
        docs = self.vectorstore.max_marginal_relevance_search(
            question, fetch_k=500, k=self.k, lambda_mult=0.5
        )
        try:
            result = self.agent.invoke({"question": question, "docs": docs})
            indices = result.get("indices", [])
        except (KeyError, OpenAIError, Exception) as e:
            logging.warning(f"[MovieRAG] Ошибка при получении ответа от модели: {e}")
            indices = list(range(min(self.k, len(docs))))  # fallback: top K первых
        return [
            {
                **sanitize_metadata(docs[i].metadata),
                "description": docs[i].page_content
            }
            for i in indices if i < len(docs)
        ]

class MovieWeaviateRecommender:
    def __init__(self,
                 weaviate_client: WeaviateClient,
                 openai_client: OpenAI,
                 model_name=MODEL_EMBS,
                 k=TOP_K,
                 collection=CLASS_NAME
                 ):
        self.weaviate_client = weaviate_client
        self.openai_client = openai_client
        self.k = k
        self.model_name = model_name
        self.collection = collection
    def recommend(self,
                  query: str,
                  year_from: int = 1900,
                  year_to: int = 2025,
                  genres: list[str] = None,
                  rating_kp: float = 0.0,
                  rating_imdb: float = 0.0
                  ):

        embedding = self.openai_client.embeddings.create(
            input=query,
            model=self.model_name
        ).data[0].embedding

        filters = Filter.by_property("year").greater_than(year_from) & \
                  Filter.by_property("year").less_than(year_to) & \
                  Filter.by_property("rating_kp").greater_than(rating_kp) & \
                  Filter.by_property("rating_imdb").greater_than(rating_imdb)

        if genres:
            filters = filters & Filter.by_property("genres").contains_any(genres)

        try:
            collection = self.weaviate_client.collections.get(self.collection)

            results = collection.query.near_vector(
                near_vector=embedding,
                limit=self.k,
                filters=filters,
                return_properties=[
                    "kp_id", "title_ru", "year", "genres",
                    "rating_kp", "rating_imdb", "page_content"
                ],
            )

            movies = [obj.properties for obj in results.objects]
            return movies

        except Exception as e:
            logger.warning(f"[MovieRAG] Ошибка запроса к Weaviate: {e}")
            return []