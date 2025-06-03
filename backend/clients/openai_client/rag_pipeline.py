import json
import math
import logging

from openai import OpenAIError
from langchain_core.runnables import RunnableMap
from langchain.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from settings import MODEL_MOVIES, TOP_K, INDEX_PATH


def sanitize_metadata(meta: dict) -> dict:
    return {
        k: (v if not isinstance(v, float) or math.isfinite(v) else None)
        for k, v in meta.items()
    }


def load_vectorstore() -> FAISS:
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.load_local(
        folder_path=INDEX_PATH,
        embeddings=embeddings,
        allow_dangerous_deserialization=True
    )
    return vectorstore


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
        docs = self.vectorstore.similarity_search(question, k=self.k)
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