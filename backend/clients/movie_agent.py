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
from models import MovieObject, MovieResponseLocalized
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
        logger.info(
            f"[MovieAgent] Начало rerank для query='{query}', locale={locale}, "
            f"входных фильмов: {len(movies)}"
        )
        
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
        rerank_yielded = []
        seen_kp_ids = set()  # Отслеживаем уже выданные фильмы для дедупликации
        rerank_duplicates_count = 0  # Счетчик дубликатов в rerank
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
                            kp_id = movie.get("kp_id")
                            
                            # Дедупликация: пропускаем фильмы, которые уже были выданы
                            if kp_id in seen_kp_ids:
                                rerank_duplicates_count += 1
                                logger.warning(
                                    f"[MovieAgent] Rerank пытается выдать дубликат: kp_id={kp_id}, "
                                    f"позиция в исходном списке={idx+1}, пропускаем"
                                )
                                continue
                            
                            seen_kp_ids.add(kp_id)
                            rerank_yielded.append(kp_id)
                            logger.debug(
                                f"[MovieAgent] Rerank выдал фильм: kp_id={kp_id}, "
                                f"позиция в исходном списке={idx+1}"
                            )
                            yield movie
                    except ValueError:
                        continue
        
        logger.info(
            f"[MovieAgent] Завершен rerank: выдано {len(rerank_yielded)} уникальных фильмов, "
            f"отфильтровано дубликатов в rerank: {rerank_duplicates_count}. "
            f"KP IDs: {rerank_yielded[:20]}{'...' if len(rerank_yielded) > 20 else ''}"
        )

    @staticmethod
    async def _get_user_excluded_kp_ids(
            user_id,
            movie_manager: MovieManager,
            platform: str = "telegram"
    ) -> Set[int]:
        skipped = await movie_manager.get_skipped(user_id, platform=platform)
        favorites = await movie_manager.get_favorites(user_id, platform=platform)
        exclude_set = set(skipped + favorites)
        duplicates_in_exclude = len(skipped) + len(favorites) - len(exclude_set)
        logger.info(
            f"[MovieAgent] Получены исключенные фильмы для user_id={user_id}, platform={platform}: "
            f"skipped={len(skipped)} фильмов {skipped[:10]}{'...' if len(skipped) > 10 else ''}, "
            f"favorites={len(favorites)} фильмов {favorites[:10]}{'...' if len(favorites) > 10 else ''}, "
            f"всего уникальных исключено: {len(exclude_set)}"
            + (f" (найдено {duplicates_in_exclude} пересечений между skipped и favorites)" if duplicates_in_exclude > 0 else "")
        )
        return exclude_set

    async def _enrich_movie(
            self,
            movie: MovieObject,
            movie_manager: MovieManager,
            session: AsyncSession,
            platform: str = "telegram",
            locale: str = "ru"
    ) -> Optional[Union[EnrichedMovieObject, MovieResponseLocalized]]:
        """
        Обогащает фильм данными из БД или Kinopoisk API.
        
        Для iOS: возвращает MovieResponseLocalized напрямую из Weaviate данных (с данными для обеих локализаций).
        Для Telegram: возвращает EnrichedMovieObject из БД или Kinopoisk API (fallback).
        
        Args:
            locale: используется только для диалога с пользователем, не влияет на возвращаемые данные
        """
        kp_id = movie.get("kp_id")
        if not kp_id:
            logger.warning(f"[MovieAgent] _enrich_movie: фильм без kp_id, пропускаем")
            return None
        
        logger.debug(
            f"[MovieAgent] Обогащаем фильм kp_id={kp_id}, platform={platform}, locale={locale}"
        )

        # Для iOS данные уже полные из Weaviate, преобразуем в MovieResponseLocalized
        if platform == "ios":
            # movie уже содержит все данные из Weaviate (Movie_v2)
            
            # Для английской локализации требуется tmdb_id (данные из TMDB)
            if locale == "en":
                tmdb_id = movie.get("tmdb_id")
                title = movie.get("title")
                tmdb_file_path = movie.get("tmdb_file_path")
                overview = movie.get("overview")
                genres_tmdb = movie.get("genres_tmdb", [])
                
                if not tmdb_id:
                    logger.warning(
                        f"[MovieAgent] _enrich_movie: фильм kp_id={kp_id} пропущен для locale=en, platform={platform}: "
                        f"отсутствует tmdb_id"
                    )
                    return None
                
                # Логируем фильмы с неполными данными для английской локализации
                if not title:
                    logger.warning(
                        f"[MovieAgent] _enrich_movie: фильм kp_id={kp_id}, tmdb_id={tmdb_id} для locale=en, platform={platform}: "
                        f"отсутствует title (название на английском)"
                    )
                
                if not tmdb_file_path:
                    logger.warning(
                        f"[MovieAgent] _enrich_movie: фильм kp_id={kp_id}, tmdb_id={tmdb_id}, title='{title or "N/A"}' "
                        f"для locale=en, platform={platform}: отсутствует tmdb_file_path (постер из TMDB) - будет сломанный постер!"
                    )
                
                if not overview:
                    logger.debug(
                        f"[MovieAgent] _enrich_movie: фильм kp_id={kp_id}, tmdb_id={tmdb_id}, title='{title or "N/A"}' "
                        f"для locale=en без overview (описание на английском)"
                    )
                
                if not genres_tmdb or len(genres_tmdb) == 0:
                    logger.debug(
                        f"[MovieAgent] _enrich_movie: фильм kp_id={kp_id}, tmdb_id={tmdb_id}, title='{title or "N/A"}' "
                        f"для locale=en без genres_tmdb (жанры на английском)"
                    )
                
            # Преобразуем жанры и страны из списка строк в список словарей для русской локализации
            genres_ru = movie.get("genres", [])
            genres_ru_dict = [{"name": g} for g in genres_ru] if genres_ru and isinstance(genres_ru[0], str) else (genres_ru or [])
            
            countries_ru = movie.get("countries", [])
            countries_ru_dict = [{"name": c} for c in countries_ru] if countries_ru and isinstance(countries_ru[0], str) else (countries_ru or [])
            
            # Преобразуем жанры и страны из списка строк в список словарей для английской локализации
            genres_tmdb = movie.get("genres_tmdb", [])
            genres_en_dict = [{"name": g} for g in genres_tmdb] if genres_tmdb and isinstance(genres_tmdb[0], str) else (genres_tmdb or [])
            
            origin_country = movie.get("origin_country", [])
            countries_en_dict = [{"name": c} for c in origin_country] if origin_country and isinstance(origin_country[0], str) else (origin_country or [])
            
            return MovieResponseLocalized(
                movie_id=kp_id,
                imdb_id=movie.get("imdb_id"),
                name=movie.get("name", ""),
                title=movie.get("title", ""),
                overview_ru=movie.get("description", ""),
                overview_en=movie.get("overview", ""),
                poster_url_kp=movie.get("kp_file_path", ""),
                poster_url_tmdb=movie.get("tmdb_file_path", ""),
                year=movie.get("year"),
                rating_kp=movie.get("rating_kp"),
                rating_imdb=movie.get("rating_imdb"),
                movie_length=movie.get("movieLength"),
                genres_ru=genres_ru_dict,
                genres_en=genres_en_dict,
                countries_ru=countries_ru_dict,
                countries_en=countries_en_dict,
                background_color_kp=movie.get("kp_background_color"),
                background_color_tmdb=movie.get("tmdb_background_color"),
            )

        # Для Telegram получаем данные из БД или Kinopoisk API
        try:
            db_movie = await asyncio.wait_for(
                movie_manager.get_by_kp_id(kp_id=kp_id), 
                timeout=5
            )
            logger.debug(
                f"[MovieAgent] Фильм kp_id={kp_id} найден в БД: title_ru={db_movie.title_ru}"
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
        except (HTTPException, asyncio.TimeoutError) as e:
            logger.warning(
                f"[MovieAgent] Фильм kp_id={kp_id} не найден в БД (ошибка: {type(e).__name__}), "
                f"пробуем Kinopoisk API"
            )
            # Fallback на Kinopoisk API только для Telegram
            try:
                kp_data = await asyncio.wait_for(self.kp_client.get_by_kp_id(kp_id=kp_id), timeout=5)
                if not kp_data:
                    logger.warning(f"[MovieAgent] Фильм kp_id={kp_id} не найден в Kinopoisk API")
                    return None
                await movie_manager.insert_movies([kp_data])
                await session.commit()
                logger.info(
                    f"[MovieAgent] Фильм kp_id={kp_id} получен из Kinopoisk API и добавлен в БД: "
                    f"title_ru={kp_data.title_ru}"
                )
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
                logger.error(f"[MovieAgent] Timeout при получении фильма kp_id={kp_id} из Kinopoisk API")
                return None

    async def answer_tool_call(self, tool_call_id: str, answer: str):
        """
        Обработка ответа пользователя на tool_call
        """
        logger.info(
            f"[MovieAgent] answer_tool_call: получен ответ пользователя на tool_call_id={tool_call_id}, "
            f"answer='{answer[:200]}...'"
        )
        
        if not self.last_tool_calls_message:
            logger.error("[MovieAgent] answer_tool_call: нет предыдущего tool_calls сообщения")
            raise RuntimeError("Нет предыдущего tool_calls сообщения")
        valid_ids = {tc["id"] for tc in self.last_tool_calls_message["tool_calls"]}
        if tool_call_id not in valid_ids:
            logger.error(
                f"[MovieAgent] answer_tool_call: tool_call_id '{tool_call_id}' не найден в последнем сообщении. "
                f"Доступные IDs: {valid_ids}"
            )
            raise RuntimeError(
                f"tool_call_id '{tool_call_id}' не найден в последнем сообщении assistant: {valid_ids}"
            )
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps({"answer": answer})
        })
        logger.debug(
            f"[MovieAgent] answer_tool_call: ответ добавлен в историю сообщений, "
            f"всего сообщений: {len(self.messages)}"
        )

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
        logger.info(
            f"[MovieAgent] run_qa: начало диалога, user_input='{user_input}', "
            f"add_user_message={add_user_message}, locale={locale}"
        )
        
        # Обновить системный промпт в зависимости от локализации
        if locale == "en":
            self.messages[0] = {"role": "system", "content": SYSTEM_PROMPT_AGENT_EN}
        else:
            self.messages[0] = {"role": "system", "content": SYSTEM_PROMPT_AGENT_RU}
        
        if user_input and add_user_message:
            self.messages.append({"role": "user", "content": user_input})
            logger.debug(f"[MovieAgent] Добавлено сообщение пользователя в историю: '{user_input[:100]}...'")

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
                    tool_name = tool_call.function.name
                    logger.info(
                        f"[MovieAgent] QA вызван tool: {tool_name}, "
                        f"tool_call_id={tool_call.id}, arguments={tool_call.function.arguments}"
                    )
                    
                    if tool_call.function.name == "ask_user_question":
                        args = json.loads(tool_call.function.arguments)
                        question = args["question"]
                        logger.info(
                            f"[MovieAgent] QA задает вопрос пользователю: '{question}'"
                        )
                        yield {
                            "type": "question",
                            "question": question,
                            "tool_call_id": tool_call.id
                        }
                        return
                    elif tool_call.function.name == "search_movies_by_vector":
                        args = json.loads(tool_call.function.arguments)
                        search_params = {
                            "query": args["query"],
                            "genres": args.get("genres", []),
                            "atmospheres": args.get("atmospheres", []),
                            "start_year": args.get("start_year", 1900),
                            "end_year": args.get("end_year", 2025)
                        }
                        logger.info(
                            f"[MovieAgent] QA запросил поиск фильмов: {search_params}"
                        )
                        yield {
                            "type": "search",
                            **search_params
                        }
                        return
            elif content:
                logger.info(
                    f"[MovieAgent] QA получил текстовый ответ от модели: '{content[:200]}...'"
                )
                self.messages.append({"role": "assistant", "content": content})
                yield {"type": "message", "content": content}
                return
            else:
                logger.error("[MovieAgent] QA получил ответ без tool_call и без текста")
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

            logger.info(
                f"[MovieAgent] run_movie_streaming: user_id={user_id}, platform={platform}, "
                f"query='{query}', genres={genres}, years={start_year}-{end_year}, "
                f"exclude_kp_ids={len(exclude_set)} фильмов"
            )

            movies = await self.recommender.recommend(
                query=query,
                genres=genres,
                start_year=start_year,
                end_year=end_year,
                exclude_kp_ids=exclude_set,
                locale=locale
            )

            logger.info(
                f"[MovieAgent] Получено {len(movies)} фильмов из recommend для user_id={user_id}. "
                f"KP IDs: {[m.get('kp_id') for m in movies[:20]]}{'...' if len(movies) > 20 else ''}"
            )

            rerank_count = 0
            enriched_count = 0
            yielded_kp_ids = set()  # Отслеживаем уже выданные фильмы в этой сессии
            skipped_duplicates = 0
            skipped_excluded = 0
            
            async for movie in self._rerank_movies_streaming(query, movies, locale=locale):
                rerank_count += 1
                kp_id = movie.get("kp_id")
                logger.debug(
                    f"[MovieAgent] Фильм после rerank #{rerank_count}: kp_id={kp_id}, "
                    f"name={movie.get('name') or movie.get('title', 'N/A')}"
                )
                
                # Проверка на дубликаты в рамках одной сессии - пропускаем
                if kp_id in yielded_kp_ids:
                    skipped_duplicates += 1
                    logger.warning(
                        f"[MovieAgent] Пропускаем дубликат фильма в одной сессии! "
                        f"kp_id={kp_id} уже был выдан ранее для user_id={user_id}"
                    )
                    continue
                
                # Проверка на то, что фильм не в exclude_set - пропускаем
                if kp_id in exclude_set:
                    skipped_excluded += 1
                    logger.warning(
                        f"[MovieAgent] Пропускаем фильм из exclude_set! "
                        f"kp_id={kp_id} находится в exclude_set для user_id={user_id}, "
                        f"но попал в результаты rerank"
                    )
                    continue
                
                enriched = await self._enrich_movie(
                    movie=movie,
                    movie_manager=movie_manager,
                    session=session,
                    platform=platform,
                    locale=locale
                )
                if enriched:
                    enriched_count += 1
                    enriched_kp_id = enriched.movie_id if hasattr(enriched, 'movie_id') else enriched.get('movie_id') if isinstance(enriched, dict) else None
                    
                    # Дополнительная проверка на дубликаты перед выдачей (на случай если kp_id изменился)
                    if enriched_kp_id in yielded_kp_ids:
                        logger.error(
                            f"[MovieAgent] КРИТИЧЕСКАЯ ОШИБКА: Пытаемся выдать дубликат фильма! "
                            f"kp_id={enriched_kp_id} уже был выдан в этой сессии для user_id={user_id}, "
                            f"пропускаем"
                        )
                        continue
                    
                    yielded_kp_ids.add(enriched_kp_id)
                    logger.info(
                        f"[MovieAgent] Выдаем фильм #{enriched_count} пользователю user_id={user_id}: "
                        f"kp_id={enriched_kp_id}, "
                        f"title={getattr(enriched, 'title_ru', None) or getattr(enriched, 'name', None) or 'N/A'}"
                    )
                    yield {"type": "movie", **enriched.model_dump()}
                else:
                    logger.warning(
                        f"[MovieAgent] Не удалось обогатить фильм kp_id={kp_id} для user_id={user_id}"
                    )
            
            logger.info(
                f"[MovieAgent] Завершена выдача фильмов для user_id={user_id}: "
                f"rerank={rerank_count}, enriched={enriched_count}, выдано={enriched_count}, "
                f"уникальных kp_ids: {len(yielded_kp_ids)}, "
                f"пропущено дубликатов после rerank: {skipped_duplicates}, "
                f"пропущено из exclude_set: {skipped_excluded}"
            )
