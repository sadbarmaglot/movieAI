import random

from typing import List, Optional
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionUserMessageParam,
)

from models import ChatQA
from settings import PROMPT_NUM_MOVIES

QUERY_STYLES = [
    "Выбери фильмы, которые стали культовыми, но малоизвестны широкой публике",
    "Подбери фильмы, которые выходили в кинотеатрах ограниченным тиражом или получили признание критиков",
    "Выдай самые необычные и нестандартные фильмы, которые не подходят под стандартные жанровые рамки",
    "Подбери фильмы, которые могли бы удивить даже киноманов",
    "Сделай список недооцененных шедевров, которые достойны большего внимания",
    "Выдай фильмы, которые завоевали награды, но не стали массово популярными",
    "Найди забытые фильмы прошлого, которые сейчас почти никто не смотрит",
    "Подбери фильмы, которые стали кассовыми провалами, но со временем приобрели культовый статус",
    "Выдай фильмы, которые раньше были запрещены к показу в некоторых странах",
    "Назови фильмы, снятые независимыми режиссерами, но достойные внимания",
    "Подбери фильмы, которые получили высокие оценки критиков, но провалились в прокате",
    "Составь список редких артхаусных фильмов, о которых мало кто слышал",
    "Выдай фильмы, которые завоевали любовь зрителей, но не получили наград",
    "Найди малоизвестные дебютные работы культовых режиссеров",
    "Выбери фильмы, которые вызвали споры и скандалы при выпуске",
    "Составь список фильмов, которые стали источником вдохновения для современных культовых картин",
    "Выдай фильмы, которые незаслуженно получили низкие оценки критиков, но любимы зрителями",
    "Подбери лучшие фильмы, снятые всего за небольшие бюджеты, но оставившие значительный след в киноиндустрии",
    "Назови фильмы, которые сложно объяснить словами, но они оставляют сильное впечатление",
    "Выдай фильмы, которые пересматриваются с каждым разом по-новому и открываются с другой стороны",
    "Подбери фильмы, в которых ключевую роль играет необычная визуальная подача или нестандартное повествование",
    "Найди фильмы, которые были выпущены в один год с крупными блокбастерами и остались незамеченными",
    "Выбери фильмы, которые вдохновили современные режиссерские хиты, но сами остались в тени",
    "Подбери фильмы с удивительными саундтреками, которые стали культовыми",
    "Выдай фильмы, которые были созданы на стыке нескольких жанров и не вписываются в стандартные категории",
    "Найди редкие фильмы, которые выходили только на VHS или не были официально переведены",
    "Выдай фильмы, в которых главную роль играют актеры, еще до того, как они стали знаменитыми",
    "Составь список фильмов, которые получили культовый статус благодаря интернету и мемам",
    "Выбери фильмы, которые были забыты со временем, но заслуживают второго шанса",
]

SYSTEM_PROMPT_QUESTIONS = ChatCompletionSystemMessageParam(
    role="system",
    content=(
        "Ты — кинокритик и ассистент, помогаешь человеку понять, какие фильмы ему подойдут. "
        "Сгенерируй 5 вопросов, которые помогут уточнить его вкус. Обращайся на ты. Ответ в JSON без лишнего текста."
    )
)

SYSTEM_PROMPT_MOVIES = ChatCompletionSystemMessageParam(
    role="system",
    content=(
        "Ты — кинокритик и ассистент. Помоги мне найти интересные фильмы на основе моих предпочтений. "
        "Не предлагай запрещённые или неуместные фильмы. "
        "Отвечай строго в формате JSON без лишнего текста."
    )
)

USER_PROMPT_QUESTIONS = ChatCompletionUserMessageParam(
    role="user",
    content=(
        'Сгенерируй ровно 5 вопросов, чтобы понять мои киновкусы. '
        'Ответь строго в формате JSON, без лишнего текста: '
        '[{"question": "Текст вопроса", "suggestions": ["Вариант 1", "Вариант 2"]}, ...]'
    )
)

def build_user_prompt(
        genres: Optional[List[str]] = None,
        atmospheres: Optional[List[str]] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        description: Optional[str] = "",
        suggestion: Optional[str] = "",
        exclude: Optional[List[str]] = None,
        favorites: Optional[List[str]] = None,
        number_movies: int = PROMPT_NUM_MOVIES
) -> ChatCompletionUserMessageParam:

    user_prompt_parts = [f"Посоветуй {number_movies} уже вышедших фильмов"]

    if genres:
        user_prompt_parts.append(f"Желаемые жанры: {', '.join(genres)}")
    if atmospheres:
        user_prompt_parts.append(f"Атмосфера: {', '.join(atmospheres)}")
    if start_year and end_year:
        user_prompt_parts.append(f"Дата выхода между {start_year} и {end_year}")
    if description:
        user_prompt_parts.append(f"Пользователь описал свой запрос так: {description}")
    if suggestion:
        user_prompt_parts.append(f"В духе фильма: {suggestion} (его самого не предлагай)")

    user_prompt_parts.append(random.choice(QUERY_STYLES))

    if favorites:
        user_prompt_parts.append(f"⚠️ Не включай фильмы из избранного: {', '.join(favorites)}")
    if exclude:
        user_prompt_parts.append(f"⚠️ Строго исключи: {', '.join(exclude)}")

    return ChatCompletionUserMessageParam(
        role="user",
        content=(
                ", ".join(user_prompt_parts) +
                '. Ответь в формате JSON: '
                '{"movies": [{"title_alt": "Только название фильма на языке оригинала без указания года выпуска"}]}'
        )
    )


def build_user_prompt_chat(
        chat_answers: Optional[List[ChatQA]] = None,
        exclude: Optional[List[str]] = None,
        favorites: Optional[List[str]] = None,
        number_movies: int = PROMPT_NUM_MOVIES
) -> ChatCompletionUserMessageParam:
    user_lines = [f"answer_{idx}: {chat.answer}" for idx, chat in enumerate(chat_answers, start=1)]
    content = ", ".join(user_lines) + ", "
    content += random.choice(QUERY_STYLES)

    if favorites:
        content += f"⚠️ Не включай избранные: {', '.join(favorites)}. "
    if exclude:
        content += f"⚠️ Строго исключи: {', '.join(exclude)}. "

    content += (
        f"Посоветуй {number_movies} уже вышедших фильмов. Ответь в формате JSON: "
        '{"movies": [{"title_alt": "Только название фильма на языке оригинала без указания года выпуска"}]}'
    )

    return ChatCompletionUserMessageParam(
        role="user",
        content=content
    )

def build_assistant_prompt(chat_answers: List[ChatQA]) -> ChatCompletionAssistantMessageParam:
    question_lines = [f"question_{idx}: {chat.question}" for idx, chat in enumerate(chat_answers, start=1)]
    content = ", ".join(question_lines) + ","

    return ChatCompletionAssistantMessageParam(
        role="assistant",
        content=content
    )