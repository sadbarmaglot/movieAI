import re
import json
import logging
import random
import traceback

from typing import List, Optional
from fastapi.responses import StreamingResponse
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionUserMessageParam,
)
from db_managers import AsyncSessionFactory, MovieManager, UserManager
from clients.kp_client import KinopoiskClient
from models import ChatQA
from settings import (
    PROMPT_NUM_MOVIES,
    TEMPERATURE_MOVIES,
    TEMPERATURE_QA,
    QUESTION_PREFIX_PATTERN,
    MOVIES_PREFIX_PATTERN,
    OVERRIDE_DATA,
    QUERY_STYLES,
)


logger = logging.getLogger(__name__)


def fix_movie_title(title):
    return re.sub(r'([a-zA-Z])(\d+)', r'\1 \2', title)


class OpenAIClient:
    def __init__(
            self,
            kp_client: KinopoiskClient,
            client: OpenAI =OpenAI(),
            model_qa: str = "gpt-4o",
            model_movies: str = "gpt-4o-mini",
            temperature_qa: float = TEMPERATURE_QA,
            temperature_movies: float = TEMPERATURE_MOVIES,
            prompt_styles: list = None,
            prompt_num_movies: int = PROMPT_NUM_MOVIES
    ):
        self.client = client
        self.kp_client = kp_client
        self.model_qa = model_qa
        self.model_movies = model_movies
        self.temperature_qa = temperature_qa
        self.temperature_movies = temperature_movies
        self.prompt_styles = prompt_styles if prompt_styles is not None else QUERY_STYLES
        self.prompt_num_movies = prompt_num_movies

    @staticmethod
    def _generate_question_prompt() -> List[ChatCompletionMessageParam]:
        system_prompt = ChatCompletionSystemMessageParam(
            role="system",
            content=(
                "Ты — кинокритик и ассистент, помогаешь человеку понять, какие фильмы ему подойдут. "
                "Сгенерируй 5 вопросов, которые помогут уточнить его вкус. Обращайся на ты. Ответ в JSON без лишнего текста."
            )
        )

        user_prompt = ChatCompletionUserMessageParam(
            role="user",
            content=(
                'Сгенерируй ровно 5 вопросов, чтобы понять мои киновкусы. '
                'Ответь строго в формате JSON, без лишнего текста: '
                '[{"question": "Текст вопроса", "suggestions": ["Вариант 1", "Вариант 2"]}, ...]'
            )
        )

        return [system_prompt, user_prompt]

    def _generate_movie_prompt(
            self,
            chat_answers: Optional[List[ChatQA]] = None,
            genres: Optional[List[str]] = None,
            atmospheres: Optional[List[str]] = None,
            start_year: Optional[int] = None,
            end_year: Optional[int] = None,
            description: Optional[str] = "",
            suggestion: Optional[str] = "",
            exclude: Optional[List[str]] = None,
            favorites: Optional[List[str]] = None,
            number_movies: int = PROMPT_NUM_MOVIES
    ) -> List[ChatCompletionMessageParam]:

        system_prompt = ChatCompletionSystemMessageParam(
            role="system",
            content=(
                "Ты — кинокритик и ассистент. Помоги мне найти интересные фильмы на основе моих предпочтений. "
                "Не предлагай запрещённые или неуместные фильмы. "
                "Отвечай строго в формате JSON без лишнего текста."
            )
        )

        if not chat_answers:
            user_prompt_parts = [f"Посоветуй {number_movies} уже вышедших фильмов"]

            if genres:
                user_prompt_parts.append(f"в жанрах {', '.join(genres)}")
            if atmospheres:
                user_prompt_parts.append(f"с атмосферой {', '.join(atmospheres)}")
            if start_year and end_year:
                user_prompt_parts.append(f"выпущенных между {start_year} и {end_year}")
            if description:
                user_prompt_parts.append(f"удовлетворяющие описанию: {description}")
            if suggestion:
                user_prompt_parts.append(f"похожие на фильм: {suggestion} (не предлагай его)")

            user_prompt_parts.append(random.choice(self.prompt_styles))

            if favorites:
                user_prompt_parts.append(f"⚠️ Не включай фильмы из избранного: {', '.join(favorites)}")
            if exclude:
                user_prompt_parts.append(f"⚠️ Строго исключи: {', '.join(exclude)}")

            user_prompt = ChatCompletionUserMessageParam(
                role="user",
                content=(
                        ", ".join(user_prompt_parts) +
                        '. Ответь в формате JSON: '
                        '{"movies": [{"title_alt": "Только название фильма на языке оригинала без указания года выпуска"}]}'
                )
            )

            return [system_prompt, user_prompt]

        assistant_lines = [f"question_{idx}: {chat.question}" for idx, chat in enumerate(chat_answers, start=1)]
        user_lines = [f"answer_{idx}: {chat.answer}" for idx, chat in enumerate(chat_answers, start=1)]

        assistant_prompt_content = ", ".join(assistant_lines) + ", "
        user_prompt_content = ", ".join(user_lines) + ", "

        user_prompt_content += random.choice(self.prompt_styles)

        if favorites:
            user_prompt_content += f"⚠️ Не включай избранные: {', '.join(favorites)}. "
        if exclude:
            user_prompt_content += f"⚠️ Строго исключи: {', '.join(exclude)}. "

        user_prompt_content += (
            f"Посоветуй {number_movies} уже вышедших фильмов. Ответь в формате JSON: "
            '{"movies": [{"title_alt": "Только название фильма на языке оригинала без указания года выпуска"}]}'
        )

        assistant_prompt = ChatCompletionAssistantMessageParam(
            role="assistant",
            content=assistant_prompt_content
        )

        user_prompt = ChatCompletionUserMessageParam(
            role="user",
            content=user_prompt_content
        )

        return [system_prompt, assistant_prompt, user_prompt]

    async def stream_questions(self) -> StreamingResponse:

        messages = self._generate_question_prompt()

        logger.debug("messages: %s", messages)

        async def stream_generator():
            buffer = ""
            try:
                response = self.client.chat.completions.create(
                    model=self.model_qa,
                    temperature=self.temperature_qa,
                    messages=messages,
                    stream=True,
                    response_format={"type": "json_object"},
                )

                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        buffer += chunk.choices[0].delta.content

                        if len(buffer) > 5000:
                            buffer = buffer[-1000:]

                        buffer = re.sub(QUESTION_PREFIX_PATTERN, "", buffer).strip()
                        matches = re.findall(r'{.*?}', buffer, re.DOTALL)
                        for match in matches:
                            try:
                                json_obj = json.loads(match)
                                buffer = buffer.replace(match, "")
                                yield json.dumps(json_obj) + "\n"
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                logger.error("OpenAI Error in question generation: %s\n%s", e, traceback.format_exc())

        return StreamingResponse(stream_generator(), media_type="application/json")

    async def stream_movies(
        self,
        user_id: int,
        chat_answers: Optional[List[ChatQA]] = None,
        genres: Optional[List[str]] = None,
        atmospheres: Optional[List[str]] = None,
        description: Optional[str] = None,
        suggestion: Optional[str] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        exclude: Optional[List[str]] = None,
        favorites: Optional[List[str]] = None,
    ) -> StreamingResponse:

        exclude = [fix_movie_title(e).strip().lower() for e in (exclude or [])]
        favorites = [fix_movie_title(f).strip().lower() for f in (favorites or [])]

        async def stream_generator():
            buffer = ""
            attempt = 0
            failed_attempt = 0
            max_attempts = 10
            max_failed_attempts = 2

            exclude_movies_set = set(exclude)
            favorites_movies_set = set(favorites)
            found_movies = set()

            async with AsyncSessionFactory() as session:
                async with session.begin():
                    user_manager = UserManager(session=session)
                    movie_manager = MovieManager(session=session)

                    await user_manager.deduct_user_stars(user_id=user_id, amount=2)

                    logger.info("🎬 Starting movie stream for user_id=%s", user_id)

                    while attempt < max_attempts:
                        messages = self._generate_movie_prompt(
                            chat_answers=chat_answers,
                            genres=genres,
                            atmospheres=atmospheres,
                            description=description,
                            suggestion=suggestion,
                            start_year=start_year,
                            end_year=end_year,
                            exclude=exclude,
                            favorites=favorites,
                            number_movies=PROMPT_NUM_MOVIES
                        )

                        logger.debug("messages: %s", messages)

                        response = self.client.chat.completions.create(
                            model=self.model_movies,
                            temperature=self.temperature_movies,
                            messages=messages,
                            stream=True,
                            response_format={"type": "json_object"}
                        )

                        for chunk in response:
                            try:
                                if chunk.choices and chunk.choices[0].delta.content:
                                    buffer += chunk.choices[0].delta.content

                                    if len(buffer) > 5000:
                                        buffer = buffer[-1000:]

                                    buffer = re.sub(MOVIES_PREFIX_PATTERN, "", buffer).strip()
                                    matches = re.findall(r'{.*?}', buffer, re.DOTALL)

                                    for match in matches:
                                        try:
                                            json_obj = json.loads(match)
                                            buffer = buffer.replace(match, "")
                                        except json.JSONDecodeError:
                                            continue

                                        original_title = json_obj["title_alt"]
                                        title = fix_movie_title(OVERRIDE_DATA.get(original_title, original_title))
                                        normalized_title = title.strip().lower()

                                        if normalized_title in exclude_movies_set or normalized_title in favorites_movies_set:
                                            continue

                                        exclude_movies_set.add(normalized_title)
                                        exclude.append(normalized_title)
                                        found_movies.add(normalized_title)

                                        selected_movie = await movie_manager.get_by_title_gpt(title_gpt=title)
                                        if selected_movie:
                                            json_obj.update(selected_movie)
                                        else:
                                            movie_details = await self.kp_client.get_by_title(title_gpt=title)
                                            if not movie_details:
                                                continue
                                            await movie_manager.insert_movies(movies_data=[movie_details])
                                            json_obj.update({
                                                **movie_details.model_dump(),
                                                "poster_url": movie_details.google_cloud_url,
                                                "movie_id": movie_details.kp_id
                                            })

                                        yield json.dumps(json_obj) + "\n"

                            except Exception as e:
                                logger.error("OpenAI Error in movies generation: %s\n%s", e, traceback.format_exc())
                                continue

                        if not found_movies:
                            failed_attempt += 1
                            if failed_attempt >= max_failed_attempts:
                                break

                        found_movies.clear()
                        attempt += 1

        return StreamingResponse(stream_generator(), media_type="application/json")