import re
import json
import logging
import traceback

from typing import List, Optional
from fastapi.responses import StreamingResponse
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from db_managers import AsyncSessionFactory, MovieManager, UserManager
from clients.kp_client import KinopoiskClient
from models import ChatQA
from clients.openai_client.prompt_templates import (
    SYSTEM_PROMPT_QUESTIONS_RU,
    SYSTEM_PROMPT_MOVIES_EN,
    USER_PROMPT_QUESTIONS_RU,
    build_user_prompt,
    build_user_prompt_chat,
    build_assistant_prompt
)
from settings import (
    MODEL_MOVIES,
    MODEL_QA,
    TEMPERATURE_MOVIES,
    TEMPERATURE_QA,
    QUESTION_PREFIX_PATTERN,
    MOVIES_PREFIX_PATTERN,
    OVERRIDE_DATA,
)


logger = logging.getLogger(__name__)


def fix_movie_title(title):
    return re.sub(r'([a-zA-Z])(\d+)', r'\1 \2', title)


class OpenAIClient:
    def __init__(
            self,
            kp_client: KinopoiskClient,
            client: OpenAI =OpenAI(),
            model_qa: str = MODEL_QA,
            model_movies: str = MODEL_MOVIES,
            temperature_qa: float = TEMPERATURE_QA,
            temperature_movies: float = TEMPERATURE_MOVIES,
    ):
        self.client = client
        self.kp_client = kp_client
        self.model_qa = model_qa
        self.model_movies = model_movies
        self.temperature_qa = temperature_qa
        self.temperature_movies = temperature_movies

    @staticmethod
    def _generate_question_prompt() -> List[ChatCompletionMessageParam]:
        return [SYSTEM_PROMPT_QUESTIONS_RU, USER_PROMPT_QUESTIONS_RU]

    @staticmethod
    def _generate_movie_prompt(
            chat_answers: Optional[List[ChatQA]] = None,
            genres: Optional[List[str]] = None,
            atmospheres: Optional[List[str]] = None,
            start_year: Optional[int] = None,
            end_year: Optional[int] = None,
            description: Optional[str] = "",
            suggestion: Optional[str] = "",
            exclude: Optional[List[str]] = None,
            favorites: Optional[List[str]] = None,
    ) -> List[ChatCompletionMessageParam]:

        if chat_answers:
            return [
                SYSTEM_PROMPT_MOVIES_EN,
                build_assistant_prompt(
                    chat_answers=chat_answers
                ),
                build_user_prompt_chat(
                    chat_answers=chat_answers,
                    exclude=exclude,
                    favorites=favorites,
                    lang="en"
                )
            ]

        return [
            SYSTEM_PROMPT_MOVIES_EN,
            build_user_prompt(
                genres=genres,
                atmospheres=atmospheres,
                start_year=start_year,
                end_year=end_year,
                description=description,
                suggestion=suggestion,
                exclude=exclude,
                favorites=favorites,
                lang="en"
            )
        ]

    async def stream_questions(self) -> StreamingResponse:

        messages = self._generate_question_prompt()

        logger.info("messages: %s", messages)

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
                    user_manager = UserManager(session)
                    await user_manager.deduct_user_stars(user_id=user_id, amount=2)
                    logger.info("✅ Stars deducted successfully for user_id=%s", user_id)

            async with AsyncSessionFactory() as session:
                async with session.begin():
                    movie_manager = MovieManager(session=session)
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
                        )

                        logger.info("messages: %s", messages)

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