import json
import logging
import asyncio
import re
import traceback

from pydantic import BaseModel
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionToolParam,
)
from typing import AsyncGenerator, List, Set, Optional, Union

from db_managers import AsyncSessionFactory, MovieManager
from clients.kp_client import KinopoiskClient
from clients.weaviate_client import MovieWeaviateRecommender
from models import MovieObject, MovieResponseLocalized
from models.movies import to_name_dicts
from settings import (
    ATMOSPHERE_MAPPING,
    CURRENT_YEAR,
    SYSTEM_PROMPT_AGENT,
    SYSTEM_PROMPT_AGENT_RU,
    SYSTEM_PROMPT_AGENT_EN,
    MODEL_QA,
    MODEL_RERANK,
    TOOLS_AGENT,
    get_agent_tools,
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
        self.kp_client = kp_client
        self.recommender = recommender
        self.system_prompt = system_prompt
        self.tools = tools
        self.model = model
        self.messages: List[dict] = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.last_tool_calls_message: Optional[dict] = None

    def inject_refinement_context(
        self,
        previous_criteria: dict = None,
        chat_history: list = None,
        locale: str = DEFAULT_LOCALE
    ):
        """
        Инжектирует контекст уточнения в историю сообщений агента.

        Используется в двух сценариях:
        1. WebSocket жив — агент уже имеет полную историю, добавляем только системное сообщение
        2. Reconnect — восстанавливаем приблизительную историю из chat_history + criteria
        """
        # Если есть chat_history — восстанавливаем историю (reconnect сценарий)
        if chat_history:
            # Сбрасываем историю до системного промпта
            self.messages = [self.messages[0]]
            for msg in chat_history:
                role = "user" if msg.get("sender") == "user" else "assistant"
                text = msg.get("text", "")
                if text:
                    self.messages.append({"role": role, "content": text})
            logger.info(
                f"[MovieAgent] Восстановлена история из chat_history: "
                f"{len(chat_history)} сообщений"
            )
        else:
            # WebSocket жив — у агента полная история, но последнее сообщение может быть
            # assistant с tool_calls без tool response (run_qa вернулся после yield search).
            # OpenAI требует tool response для каждого tool_call_id — добавляем.
            if (self.messages
                    and self.messages[-1].get("role") == "assistant"
                    and self.messages[-1].get("tool_calls")):
                for tc in self.messages[-1]["tool_calls"]:
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": "Search completed. Results were shown to the user."
                    })

        # Формируем системное сообщение об уточнении
        refinement_text = (
            "Пользователь просмотрел рекомендованные фильмы и хочет уточнить поиск. "
            "Сохрани все предыдущие критерии (жанры, атмосферу, годы и т.д.) как базу. "
            "Меняй или добавляй только то, что пользователь явно просит изменить. "
            "Если пользователь добавляет новый жанр — объедини его с предыдущими, а не заменяй. "
            "Выполни поиск сразу, без дополнительных вопросов, если запрос пользователя достаточно ясен."
        ) if locale != "en" else (
            "The user has reviewed the recommended movies and wants to refine the search. "
            "Keep all previous criteria (genres, atmosphere, years, etc.) as the base. "
            "Only change or add what the user explicitly asks to modify. "
            "If the user adds a new genre — combine it with the previous ones, don't replace. "
            "Perform the search immediately without extra questions if the user's request is clear enough."
        )

        if previous_criteria:
            criteria_parts = []
            if previous_criteria.get("query"):
                criteria_parts.append(f"query: {previous_criteria['query']}")
            if previous_criteria.get("genres"):
                criteria_parts.append(f"genres: {', '.join(previous_criteria['genres'])}")
            if previous_criteria.get("start_year") and previous_criteria.get("end_year"):
                criteria_parts.append(f"years: {previous_criteria['start_year']}-{previous_criteria['end_year']}")
            if previous_criteria.get("cast"):
                criteria_parts.append(f"cast: {', '.join(previous_criteria['cast'])}")
            if previous_criteria.get("directors"):
                criteria_parts.append(f"directors: {', '.join(previous_criteria['directors'])}")
            if criteria_parts:
                criteria_summary = "; ".join(criteria_parts)
                if locale != "en":
                    refinement_text += f"\nПредыдущие критерии поиска: {criteria_summary}"
                else:
                    refinement_text += f"\nPrevious search criteria: {criteria_summary}"

        self.messages.append({"role": "system", "content": refinement_text})
        logger.info(
            f"[MovieAgent] Инжектирован контекст уточнения, "
            f"всего сообщений: {len(self.messages)}"
        )

    @staticmethod
    def _get_movie_name(movie: dict, locale: str = "ru") -> str:
        """Возвращает название фильма с учётом локали (с fallback)."""
        name = movie.get("name", "") if locale == "ru" else movie.get("title", "")
        if not name:
            name = movie.get("title", "") or movie.get("name", "")
        return name

    @staticmethod
    def _format_movies_for_rerank(movies: List[MovieObject], locale: str = "ru") -> str:
        lines = []
        for i, m in enumerate(movies):
            name = MovieAgent._get_movie_name(m, locale)
            lines.append(f"{i + 1}. [{name}] {m['page_content'][:200]}")
        return "\n".join(lines)

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Нормализует название для сравнения франшиз."""
        t = title.lower().strip()
        t = re.sub(r'\s*[:]\s*.*$', '', t)     # "Matrix: Reloaded" -> "matrix"
        t = re.sub(r'\s+\d+$', '', t)           # "Matrix 2" -> "matrix"
        t = re.sub(r'\s+[ivxlc]+$', '', t, flags=re.IGNORECASE)  # "Rocky IV" -> "rocky"
        return t.strip()

    @staticmethod
    def _pre_filter_franchise(
        movies: List[MovieObject],
        source_name: str,
        locale: str = "ru"
    ) -> List[MovieObject]:
        """Убирает из списка фильмы с совпадающим названием (исходный фильм, сиквелы)."""
        source_norm = MovieAgent._normalize_title(source_name)
        if not source_norm:
            return movies

        filtered = []
        for m in movies:
            name = MovieAgent._get_movie_name(m, locale)
            movie_norm = MovieAgent._normalize_title(name)
            if movie_norm and movie_norm == source_norm:
                logger.info(f"[MovieAgent] Pre-filter: исключаем '{name}' (франшиза '{source_name}')")
                continue
            filtered.append(m)

        removed = len(movies) - len(filtered)
        if removed:
            logger.info(f"[MovieAgent] Pre-filter франшизы: убрано {removed} фильмов для '{source_name}'")
        return filtered

    async def _rerank_movies_streaming(
            self,
            query: str,
            movies: List[MovieObject],
            locale: str = DEFAULT_LOCALE,
            source_movie_name: str | None = None,
            genres: list[str] | None = None,
    ) -> AsyncGenerator[MovieObject, None]:
        logger.info(
            f"[MovieAgent] Начало rerank для query='{query}', locale={locale}, "
            f"входных фильмов: {len(movies)}, source_movie_name={source_movie_name}"
        )

        # Построить exclude_instruction
        if source_movie_name:
            if locale == "en":
                exclude_instruction = (
                    f'⚠️ EXCLUDE the movie "{source_movie_name}" and its sequels, '
                    f"prequels, remakes, and spin-offs. Do NOT include their numbers."
                )
            else:
                exclude_instruction = (
                    f'⚠️ ИСКЛЮЧИ из результата фильм «{source_movie_name}», а также '
                    f"его сиквелы, приквелы, ремейки и спин-оффы. НЕ включай их номера в ответ."
                )
        else:
            exclude_instruction = ""

        # Построить criteria_context
        criteria_parts = []
        if genres:
            genre_label = "Genres" if locale == "en" else "Жанры"
            criteria_parts.append(f"{genre_label}: {', '.join(genres)}")
        criteria_context = "\n".join(criteria_parts)

        # Выбрать промпт в зависимости от локализации
        rerank_template = RERANK_PROMPT_TEMPLATE_EN if locale == "en" else RERANK_PROMPT_TEMPLATE_RU
        rerank_prompt = rerank_template.format(
            query=query,
            movies_list=self._format_movies_for_rerank(movies, locale),
            movies_count=len(movies),
            exclude_instruction=exclude_instruction,
            criteria_context=criteria_context,
        )

        # Выбрать системный промпт в зависимости от локализации
        system_content = "You are a movie recommendation assistant." if locale == "en" else "Ты помощник по подбору фильмов."

        response = await asyncio.wait_for(
            self.openai_client.chat.completions.create(
                model=MODEL_RERANK,
                messages=[
                    ChatCompletionSystemMessageParam(role="system", content=system_content),
                    ChatCompletionUserMessageParam(role="user", content=rerank_prompt)
                ],
                stream=True,
            ),
            timeout=30,
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

    @staticmethod
    def _enrich_movie(
            movie: MovieObject,
            platform: str = "telegram",
            locale: str = "ru"
    ) -> Optional[Union[EnrichedMovieObject, MovieResponseLocalized]]:
        """
        Преобразует данные Weaviate в объект для клиента.

        Для iOS: MovieResponseLocalized (оба языка).
        Для Telegram: EnrichedMovieObject.
        """
        kp_id = movie.get("kp_id")
        if not kp_id:
            logger.warning(f"[MovieAgent] _enrich_movie: фильм без kp_id, пропускаем")
            return None

        if platform == "ios":
            if locale == "en" and not movie.get("tmdb_id"):
                return None

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
                genres_ru=to_name_dicts(movie.get("genres", [])),
                genres_en=to_name_dicts(movie.get("genres_tmdb", [])),
                countries_ru=to_name_dicts(movie.get("countries", [])),
                countries_en=to_name_dicts(movie.get("origin_country", [])),
                background_color_kp=movie.get("kp_background_color"),
                background_color_tmdb=movie.get("tmdb_background_color"),
            )

        # Telegram — данные из Weaviate напрямую
        return EnrichedMovieObject(
            movie_id=kp_id,
            title_ru=movie.get("name", ""),
            title_alt=movie.get("title", ""),
            overview=movie.get("description", ""),
            year=movie.get("year", 0),
            poster_url=movie.get("kp_file_path", ""),
            rating_kp=movie.get("rating_kp", 0.0),
            rating_imdb=movie.get("rating_imdb", 0.0),
            genres=to_name_dicts(movie.get("genres", [])),
            background_color=movie.get("kp_background_color"),
        )

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
        
        # Обновить системный промпт и инструменты в зависимости от локализации
        if locale == "en":
            self.messages[0] = {"role": "system", "content": SYSTEM_PROMPT_AGENT_EN}
        else:
            self.messages[0] = {"role": "system", "content": SYSTEM_PROMPT_AGENT_RU}
        self.tools = get_agent_tools(locale)
        
        if user_input and add_user_message:
            self.messages.append({"role": "user", "content": user_input})
            logger.debug(f"[MovieAgent] Добавлено сообщение пользователя в историю: '{user_input[:100]}...'")

        while True:
            try:
                response = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model=self.model,
                        messages=self.messages,
                        tools=self.tools,
                        tool_choice="auto"
                    ),
                    timeout=30
                )
            except Exception as e:
                logger.error(
                    f"[MovieAgent] Ошибка при вызове OpenAI API: {type(e).__name__}: {str(e)}\n"
                    f"Messages count: {len(self.messages)}\n"
                    f"Last 3 messages: {self.messages[-3:] if len(self.messages) >= 3 else self.messages}\n"
                    f"Traceback: {traceback.format_exc()}"
                )
                raise

            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)
            content = getattr(message, "content", None)
            
            # Детальное логирование для отладки
            logger.debug(
                f"[MovieAgent] Ответ от OpenAI: tool_calls={tool_calls is not None and len(tool_calls) > 0 if tool_calls else False}, "
                f"content={'present' if content else 'None'}, "
                f"content_length={len(content) if content else 0}, "
                f"message_keys={list(message.model_dump().keys()) if hasattr(message, 'model_dump') else 'N/A'}"
            )

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
                        suggestions = args.get("suggestions", [])
                        logger.info(
                            f"[MovieAgent] QA задает вопрос пользователю: '{question}', "
                            f"suggestions={suggestions}"
                        )
                        yield {
                            "type": "question",
                            "question": question,
                            "suggestions": suggestions,
                            "tool_call_id": tool_call.id
                        }
                        return
                    elif tool_call.function.name == "suggest_movie_titles":
                        args = json.loads(tool_call.function.arguments)
                        titles = args.get("titles", [])
                        base_query = args.get("query", "")
                        
                        # Формируем улучшенный query с названиями фильмов
                        if titles:
                            titles_str = ", ".join(titles)
                            enhanced_query = f"{base_query} похожие на: {titles_str}"
                            logger.info(
                                f"[MovieAgent] QA предложил названия фильмов: {titles}, "
                                f"улучшенный query: '{enhanced_query[:200]}...'"
                            )
                        else:
                            enhanced_query = base_query
                            logger.warning(
                                f"[MovieAgent] suggest_movie_titles вызван без названий, "
                                f"используем только base_query"
                            )
                        
                        search_params = {
                            "query": enhanced_query,
                            "genres": args.get("genres", []),
                            "atmospheres": args.get("atmospheres", []),
                            "start_year": args.get("start_year", 1900),
                            "end_year": args.get("end_year", CURRENT_YEAR),
                            "cast": args.get("cast", []),
                            "directors": args.get("directors", []),
                            "rating_kp": args.get("rating_kp", 0.0),
                            "rating_imdb": args.get("rating_imdb", 0.0),
                            "suggested_titles": titles  # Сохраняем для логирования
                        }
                        logger.info(
                            f"[MovieAgent] QA запросил поиск фильмов с предложенными названиями: {search_params}"
                        )
                        yield {
                            "type": "search",
                            **search_params
                        }
                        return
                    elif tool_call.function.name == "search_movies_by_vector":
                        args = json.loads(tool_call.function.arguments)
                        search_params = {
                            "query": args.get("query", ""),
                            "movie_name": args.get("movie_name"),
                            "genres": args.get("genres", []),
                            "atmospheres": args.get("atmospheres", []),
                            "start_year": args.get("start_year", 1900),
                            "end_year": args.get("end_year", CURRENT_YEAR),
                            "cast": args.get("cast", []),
                            "directors": args.get("directors", []),
                            "rating_kp": args.get("rating_kp", 0.0),
                            "rating_imdb": args.get("rating_imdb", 0.0)
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
                logger.warning(
                    f"[MovieAgent] QA получил текстовый ответ от модели вместо использования инструмента: '{content[:200]}...'"
                )
                logger.info(
                    f"[MovieAgent] Преобразуем текстовый ответ в вопрос через ask_user_question"
                )
                # Добавляем текстовый ответ ассистента в историю сообщений
                self.messages.append({"role": "assistant", "content": content})
                logger.debug(
                    f"[MovieAgent] Текстовый ответ ассистента добавлен в историю сообщений, "
                    f"всего сообщений: {len(self.messages)}"
                )
                yield {
                    "type": "question",
                    "question": content,
                    "suggestions": [],  # Пустой массив, так как это fallback случай
                    "tool_call_id": None
                }
                return
            else:
                # Детальное логирование для отладки
                logger.error(
                    f"[MovieAgent] QA получил ответ без tool_call и без текста. "
                    f"Response details: message={message}, "
                    f"message_type={type(message)}, "
                    f"response_choices_count={len(response.choices)}, "
                    f"response_finish_reason={response.choices[0].finish_reason if response.choices else 'N/A'}"
                )
                # Пробуем добавить сообщение в историю и повторить запрос один раз
                if len(self.messages) < 20:  # Защита от бесконечного цикла
                    logger.warning(
                        f"[MovieAgent] Пробуем повторить запрос. "
                        f"Текущее количество сообщений: {len(self.messages)}"
                    )
                    # Добавляем системное сообщение с просьбой использовать инструменты
                    self.messages.append({
                        "role": "system", 
                        "content": "Пожалуйста, используй один из доступных инструментов (ask_user_question, suggest_movie_titles, search_movies_by_vector). Не отвечай текстом напрямую."
                    })
                    continue  # Повторяем цикл
                else:
                    raise RuntimeError("Ответ без tool_call и без текста после нескольких попыток")

    async def run_movie_streaming(
            self,
            user_id,
            platform: str = "telegram",
            locale: str = "ru",
            query: str = None,
            genres: list = None,
            atmospheres: list = None,
            start_year: int = None,
            end_year: int = None,
            cast: list = None,
            directors: list = None,
            suggested_titles: list = None,
            movie_name: str = None,
            rating_kp: float = 0.0,
            rating_imdb: float = 0.0
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
                f"query='{query}', movie_name='{movie_name}', genres={genres}, years={start_year}-{end_year}, "
                f"cast={cast}, directors={directors}, exclude_kp_ids={len(exclude_set)} фильмов, "
                f"suggested_titles={suggested_titles}, rating_kp={rating_kp}, rating_imdb={rating_imdb}"
            )

            movies = await self.recommender.recommend(
                query=query,
                genres=genres,
                start_year=start_year,
                end_year=end_year,
                cast=cast,
                directors=directors,
                exclude_kp_ids=exclude_set,
                locale=locale,
                suggested_titles=suggested_titles,
                movie_name=movie_name,
                rating_kp=rating_kp,
                rating_imdb=rating_imdb
            )

            logger.info(
                f"[MovieAgent] Получено {len(movies)} фильмов из recommend для user_id={user_id}. "
                f"KP IDs: {[m.get('kp_id') for m in movies[:20]]}{'...' if len(movies) > 20 else ''}"
            )

            # Pre-filter франшизы перед реранком (только для "похожих на X", не для прямого поиска)
            if movie_name and query and query.strip():
                movies = self._pre_filter_franchise(movies, movie_name, locale)

            rerank_count = 0
            enriched_count = 0
            yielded_kp_ids = set()  # Отслеживаем уже выданные фильмы в этой сессии
            skipped_duplicates = 0
            skipped_excluded = 0

            # Реранк с fallback на прямую итерацию при ошибке
            reranked_movies = []
            try:
                async for movie in self._rerank_movies_streaming(
                    query, movies, locale=locale,
                    source_movie_name=movie_name,
                    genres=genres,
                ):
                    reranked_movies.append(movie)
            except Exception as e:
                logger.error(
                    f"[MovieAgent] Ошибка rerank (выдано {len(reranked_movies)} фильмов): {e}, "
                    f"fallback на оставшиеся фильмы"
                )

            # Дополнить фильмами, которые реранк не вернул (модель может вернуть не все)
            if len(reranked_movies) < len(movies):
                reranked_kp_ids = {m.get("kp_id") for m in reranked_movies}
                remaining = [m for m in movies if m.get("kp_id") not in reranked_kp_ids]
                if remaining:
                    logger.info(
                        f"[MovieAgent] Rerank вернул {len(reranked_movies)}/{len(movies)}, "
                        f"дополняем {len(remaining)} фильмами в исходном порядке"
                    )
                    reranked_movies.extend(remaining)

            for movie in reranked_movies:
                rerank_count += 1
                kp_id = movie.get("kp_id")
                logger.debug(
                    f"[MovieAgent] Обработка фильма: kp_id={kp_id}, "
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
                
                # Проверка на exclude_set (пропускаем только для рекомендаций, не для прямого поиска)
                is_direct_search = movie_name and (not query or not query.strip())
                if kp_id in exclude_set and not is_direct_search:
                    skipped_excluded += 1
                    logger.warning(
                        f"[MovieAgent] Пропускаем фильм из exclude_set! "
                        f"kp_id={kp_id} находится в exclude_set для user_id={user_id}"
                    )
                    continue
                
                enriched = self._enrich_movie(
                    movie=movie,
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
                f"из recommend={len(movies)}, rerank={rerank_count}, enriched={enriched_count}, "
                f"уникальных kp_ids: {len(yielded_kp_ids)}, "
                f"пропущено дубликатов: {skipped_duplicates}, "
                f"пропущено из exclude_set: {skipped_excluded}"
            )
