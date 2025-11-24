import json
import logging
import asyncio

from pydantic import BaseModel
from fastapi import HTTPException
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionToolParam,
)
from typing import AsyncGenerator, List, Set, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession

from db_managers import AsyncSessionFactory, MovieManager
from clients.kp_client import KinopoiskClient
from clients.weaviate_client import MovieWeaviateRecommender
from models import MovieObject, MovieResponseRU, MovieResponseEN
from settings import (
    ATMOSPHERE_MAPPING,
    SYSTEM_PROMPT_AGENT,
    SYSTEM_PROMPT_AGENT_RU,
    SYSTEM_PROMPT_AGENT_EN,
    MODEL_QA,
    TOOLS_AGENT,
    RERANK_PROMPT_TEMPLATE_RU,
    RERANK_PROMPT_TEMPLATE_EN,
    DEFAULT_LOCALE
)

logger = logging.getLogger(__name__)

class EnrichedMovieObject(BaseModel):
    movie_id: int
    title_ru: str
    title_alt: str
    overview: str
    year: int
    genres: Optional[List[dict]] = None
    rating_kp: float
    rating_imdb: float
    poster_url: str
    background_color: Optional[str]

class MovieAgent:
    def __init__(self,
                 openai_client: AsyncOpenAI,
                 kp_client: KinopoiskClient,
                 recommender: MovieWeaviateRecommender,
                 system_prompt: str = SYSTEM_PROMPT_AGENT,
                 tools: List[ChatCompletionToolParam] = TOOLS_AGENT,
                 model: str = MODEL_QA
                 ):
        self.openai_client = openai_client
        self.kp_client =kp_client
        self.recommender = recommender
        self.system_prompt = system_prompt
        self.tools = tools
        self.model = model
        self.messages: List[dict] = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.last_tool_calls_message: Optional[dict] = None

    @staticmethod
    def _format_movies_for_rerank(movies: List[MovieObject]) -> str:
        return "\n".join(
            f"{i + 1}. {m['page_content'][:200]}" for i, m in enumerate(movies)
        )

    async def _rerank_movies_streaming(
            self, 
            query: str, 
            movies: List[MovieObject],
            locale: str = DEFAULT_LOCALE
    ) -> AsyncGenerator[MovieObject, None]:
        # Выбрать промпт в зависимости от локализации
        rerank_template = RERANK_PROMPT_TEMPLATE_EN if locale == "en" else RERANK_PROMPT_TEMPLATE_RU
        rerank_prompt = rerank_template.format(
            query=query,
            movies_list=self._format_movies_for_rerank(movies)
        )

        # Выбрать системный промпт в зависимости от локализации
        system_content = "You are a movie recommendation assistant." if locale == "en" else "Ты помощник по подбору фильмов."

        response = await self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                ChatCompletionSystemMessageParam(role="system", content=system_content),
                ChatCompletionUserMessageParam(role="user", content=rerank_prompt)
            ],
            stream=True,
        )

        buffer = ""
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                buffer += chunk.choices[0].delta.content
                lines = buffer.split("\n")
                buffer = lines.pop()

                for line in lines:
                    try:
                        idx = int(line.strip()) - 1
                        if 0 <= idx < len(movies):
                            movie = movies[idx]
                            yield movie
                    except ValueError:
                        continue

    @staticmethod
    async def _get_user_excluded_kp_ids(
            user_id,
            movie_manager: MovieManager,
            platform: str = "telegram"
    ) -> Set[int]:
        skipped = await movie_manager.get_skipped(user_id, platform=platform)
        favorites = await movie_manager.get_favorites(user_id, platform=platform)
        return set(skipped + favorites)

    async def _enrich_movie(
            self,
            movie: MovieObject,
            movie_manager: MovieManager,
            session: AsyncSession,
            platform: str = "telegram",
            locale: str = "ru"
    ) -> Optional[Union[EnrichedMovieObject, MovieResponseRU, MovieResponseEN]]:
        """
        Обогащает фильм данными из БД или Kinopoisk API.
        
        Для iOS: возвращает MovieResponseRU или MovieResponseEN напрямую из Weaviate данных.
        Для Telegram: возвращает EnrichedMovieObject из БД или Kinopoisk API (fallback).
        """
        kp_id = movie.get("kp_id")
        if not kp_id:
            return None

        # Для iOS данные уже полные из Weaviate, преобразуем в MovieResponseRU/EN
        if platform == "ios":
            # movie уже содержит все данные из Weaviate (Movie_v2)
            if locale == "en":
                # Для английской локализации требуется tmdb_id (данные из TMDB)
                if not movie.get("tmdb_id"):
                    return None  # Пропускаем фильм без данных для английской локализации
                
                logger.info(f"[_enrich_movie] ✅ iOS EN: Возвращаем MovieResponseEN для kp_id={kp_id}, tmdb_id={movie.get('tmdb_id')}")
                
                # Преобразуем жанры и страны из списка строк в список словарей
                genres_tmdb = movie.get("genres_tmdb", [])
                genres = [{"name": g} for g in genres_tmdb] if genres_tmdb and isinstance(genres_tmdb[0], str) else genres_tmdb
                
                origin_country = movie.get("origin_country", [])
                countries = [{"name": c} for c in origin_country] if origin_country and isinstance(origin_country[0], str) else origin_country
                
                return MovieResponseEN(
                    movie_id=kp_id,
                    imdb_id=movie.get("imdb_id"),
                    title=movie.get("title", ""),  # только английское название
                    overview=movie.get("overview", ""),  # только английское описание
                    poster_url=movie.get("tmdb_file_path", ""),  # только постер из TMDB
                    year=movie.get("year"),
                    rating_kp=movie.get("rating_kp"),
                    rating_imdb=movie.get("rating_imdb"),
                    movie_length=movie.get("movieLength"),
                    genres=genres,  # только английские жанры в формате [{"name": "..."}]
                    countries=countries,  # только английские страны в формате [{"name": "..."}]
                    background_color=movie.get("tmdb_background_color"),  # только цвет фона из TMDB
                )
            else:  # ru
                # Преобразуем жанры и страны из списка строк в список словарей
                genres_ru = movie.get("genres", [])
                genres = [{"name": g} for g in genres_ru] if genres_ru and isinstance(genres_ru[0], str) else genres_ru
                
                countries_ru = movie.get("countries", [])
                countries = [{"name": c} for c in countries_ru] if countries_ru and isinstance(countries_ru[0], str) else countries_ru
                
                return MovieResponseRU(
                    movie_id=kp_id,
                    name=movie.get("name", ""),  # только русское название
                    title=movie.get("title", ""),  # английское название
                    overview=movie.get("description", ""),  # только русское описание
                    poster_url=movie.get("kp_file_path", ""),  # только постер из Кинопоиска
                    year=movie.get("year"),
                    rating_kp=movie.get("rating_kp"),
                    rating_imdb=movie.get("rating_imdb"),
                    movie_length=movie.get("movieLength"),
                    genres=genres,  # только русские жанры в формате [{"name": "..."}]
                    countries=countries,  # только русские страны в формате [{"name": "..."}]
                    background_color=movie.get("kp_background_color"),  # только цвет фона из Кинопоиска
                )

        # Для Telegram получаем данные из БД или Kinopoisk API
        try:
            db_movie = await asyncio.wait_for(
                movie_manager.get_by_kp_id(kp_id=kp_id), 
                timeout=5
            )
            return EnrichedMovieObject(
                movie_id=db_movie.movie_id,
                title_ru=db_movie.title_ru,
                title_alt=db_movie.title_alt,
                overview=db_movie.overview,
                year=db_movie.year,
                poster_url=db_movie.poster_url,
                rating_kp=db_movie.rating_kp,
                rating_imdb=db_movie.rating_imdb,
                genres=db_movie.genres,
                background_color=db_movie.background_color
            )
        except (HTTPException, asyncio.TimeoutError):
            # Fallback на Kinopoisk API только для Telegram
            try:
                kp_data = await asyncio.wait_for(self.kp_client.get_by_kp_id(kp_id=kp_id), timeout=5)
                if not kp_data:
                    return None
                await movie_manager.insert_movies([kp_data])
                await session.commit()
                return EnrichedMovieObject(
                    movie_id=kp_data.kp_id,
                    title_ru=kp_data.title_ru,
                    title_alt=kp_data.title_alt,
                    overview=kp_data.overview,
                    year=kp_data.year,
                    poster_url=kp_data.google_cloud_url,
                    rating_kp=kp_data.rating_kp,
                    rating_imdb=kp_data.rating_imdb,
                    genres=kp_data.genres,
                    background_color=kp_data.background_color
                )
            except asyncio.TimeoutError:
                return None

    async def answer_tool_call(self, tool_call_id: str, answer: str):
        """
        Обработка ответа пользователя на tool_call
        """
        if not self.last_tool_calls_message:
            raise RuntimeError("Нет предыдущего tool_calls сообщения")
        valid_ids = {tc["id"] for tc in self.last_tool_calls_message["tool_calls"]}
        if tool_call_id not in valid_ids:
            raise RuntimeError(
                f"tool_call_id '{tool_call_id}' не найден в последнем сообщении assistant: {valid_ids}"
            )
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps({"answer": answer})
        })

    async def run_qa(
            self,
            user_input: str,
            add_user_message: bool = True,
            locale: str = DEFAULT_LOCALE
    ) -> AsyncGenerator[dict, None]:
        """
        Диалог с пользователем: задаём вопросы, принимаем ответы.
        
        Args:
            locale: 'ru' or 'en' - локализация для промпта и ответов
        """
        # Обновить системный промпт в зависимости от локализации
        if locale == "en":
            self.messages[0] = {"role": "system", "content": SYSTEM_PROMPT_AGENT_EN}
        else:
            self.messages[0] = {"role": "system", "content": SYSTEM_PROMPT_AGENT_RU}
        
        if user_input and add_user_message:
            self.messages.append({"role": "user", "content": user_input})

        while True:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=self.tools,
                tool_choice="auto"
            )

            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)
            content = getattr(message, "content", None)

            if tool_calls:
                tool_calls_dict = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in tool_calls
                ]
                self.last_tool_calls_message = {"role": "assistant", "tool_calls": tool_calls_dict}
                self.messages.append(self.last_tool_calls_message)

                for tool_call in tool_calls:
                    if tool_call.function.name == "ask_user_question":
                        args = json.loads(tool_call.function.arguments)
                        yield {
                            "type": "question",
                            "question": args["question"],
                            "tool_call_id": tool_call.id
                        }
                        return
                    elif tool_call.function.name == "search_movies_by_vector":
                        args = json.loads(tool_call.function.arguments)
                        yield {
                            "type": "search",
                            "query": args["query"],
                            "genres": args.get("genres", []),
                            "atmospheres": args.get("atmospheres", []),
                            "start_year": args.get("start_year", 1900),
                            "end_year": args.get("end_year", 2025)
                        }
                        return
            elif content:
                self.messages.append({"role": "assistant", "content": content})
                yield {"type": "message", "content": content}
                return
            else:
                raise RuntimeError("Ответ без tool_call и без текста")

    async def run_movie_streaming(
            self,
            user_id,
            platform: str = "telegram",
            locale: str = "ru",
            query: str = None,
            genres: list = None,
            atmospheres: list = None,
            start_year: int = None,
            end_year: int = None
    ) -> AsyncGenerator[dict, None]:
        """
        Поиск фильмов на основе финального запроса
        
        Args:
            user_id: ID пользователя (int для Telegram) или device_id (str для iOS)
            platform: 'telegram' or 'ios'
            locale: 'ru' or 'en' - локализация клиента
        """
        # Инициализируем query пустой строкой, если он None
        if query is None:
            query = ""
        
        if atmospheres is not None:
            atmosphere_text = ", ".join(ATMOSPHERE_MAPPING.get(a, "") for a in atmospheres)
            if atmosphere_text:
                if query:
                    query += ", " + atmosphere_text
                else:
                    query = atmosphere_text

        async with AsyncSessionFactory() as session:
            movie_manager = MovieManager(session)
            exclude_set = await self._get_user_excluded_kp_ids(
                user_id=user_id, 
                movie_manager=movie_manager,
                platform=platform
            )

            movies = await self.recommender.recommend(
                query=query,
                genres=genres,
                start_year=start_year,
                end_year=end_year,
                exclude_kp_ids=exclude_set,
                locale=locale
            )

            async for movie in self._rerank_movies_streaming(query, movies, locale=locale):
                enriched = await self._enrich_movie(
                    movie=movie,
                    movie_manager=movie_manager,
                    session=session,
                    platform=platform,
                    locale=locale
                )
                if enriched:
                    yield {"type": "movie", **enriched.model_dump()}
