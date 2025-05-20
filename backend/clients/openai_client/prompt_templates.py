import random

from typing import List, Optional
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionUserMessageParam,
)

from models import ChatQA
from settings import PROMPT_NUM_MOVIES

GENRE_TRANSLATIONS = {
    "комедия": "comedy",
    "мультфильм": "animation",
    "ужасы": "horror",
    "фэнтези": "fantasy",
    "научная фантастика": "sci-fi",
    "триллер": "thriller",
    "боевик": "action",
    "мелодрама": "romance",
    "драма": "drama",
    "детектив": "mystery",
    "приключение": "adventure",
    "военный": "war",
    "семейный": "family",
    "документальный": "documentary",
    "историчекий": "historical",
    "криминал": "crime",
    "биография": "biography",
    "вестерн": "western",
    "спортивный": "sports",
    "музыка": "musical",
    "любой": "any"
}

ATMOSPHERE_TRANSLATIONS = {
    "про любовь": "about love",
    "душевный и трогательный": "touching and heartfelt",
    "динамичный и напряженный": "dynamic and intense",
    "жизнеутверждающий": "uplifting",
    "мрачный и атмосферный": "dark and atmospheric",
    "сюрреалистичный": "surreal",
    "психологический": "psychological",
    "медитативный": "meditative",
    "депрессивный": "depressive",
    "любой": "any"
}

QUERY_STYLES_RU = [
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

QUERY_STYLES_EN = [
    "Choose cult films that are little known to the general public",
    "Suggest films that had a limited theatrical release or received critical acclaim",
    "List the most unusual and unconventional films that don't fit into standard genres",
    "Pick movies that could surprise even seasoned cinephiles",
    "Create a list of underrated masterpieces that deserve more attention",
    "Recommend films that won awards but didn't gain mainstream popularity",
    "Find forgotten movies from the past that hardly anyone watches anymore",
    "Suggest box office flops that later gained cult status",
    "Name films that were once banned in certain countries",
    "Select independent films by lesser-known directors that deserve attention",
    "Suggest films praised by critics but that failed at the box office",
    "List rare arthouse films that few people have heard of",
    "Recommend films beloved by audiences but overlooked by awards",
    "Find early debut works of now-famous directors that flew under the radar",
    "Choose movies that sparked controversy or scandal upon release",
    "List films that inspired today’s cult classics but remain in the shadows",
    "Recommend movies unfairly rated poorly by critics but loved by fans",
    "Suggest impressive low-budget films that left a significant mark on cinema",
    "Name movies that are hard to explain but leave a strong impression",
    "Suggest films that reveal something new with each rewatch",
    "Pick films that rely heavily on unique visuals or unconventional storytelling",
    "Find movies released in the same year as blockbusters but overlooked",
    "Choose hidden gems that inspired modern director hits",
    "Suggest movies with iconic and unforgettable soundtracks",
    "List films that blend multiple genres and defy categorization",
    "Find rare titles released only on VHS or never officially translated",
    "Name movies starring actors before they became famous",
    "List cult classics that gained popularity through the internet and memes",
    "Pick films that were forgotten over time but deserve a second chance",
]
SYSTEM_PROMPT_QUESTIONS_RU = ChatCompletionSystemMessageParam(
    role="system",
    content=(
        "Ты — кинокритик и ассистент, помогаешь человеку понять, какие фильмы ему подойдут. "
        "Сгенерируй 5 вопросов, которые помогут уточнить его вкус. Обращайся на ты. Ответ в JSON без лишнего текста."
    )
)

SYSTEM_PROMPT_QUESTIONS_EN = ChatCompletionSystemMessageParam(
    role="system",
    content=(
        "You are a film critic assistant helping a person discover their movie preferences. "
        "Generate 5 questions to help clarify their taste. Use casual tone. Answer in JSON only, no extra text."
    )
)

SYSTEM_PROMPT_MOVIES_RU = ChatCompletionSystemMessageParam(
    role="system",
    content=(
        "Ты — кинокритик и ассистент. Помоги мне найти интересные фильмы на основе моих предпочтений. "
        "Не предлагай запрещённые или неуместные фильмы. "
        "Отвечай строго в формате JSON без лишнего текста."
    )
)


SYSTEM_PROMPT_MOVIES_EN = ChatCompletionSystemMessageParam(
    role="system",
    content=(
        "You are a film critic assistant. Help me find interesting movies based on my preferences. "
        "Do not suggest inappropriate or banned content. Respond in JSON only, no extra text."
    )
)

USER_PROMPT_QUESTIONS_RU = ChatCompletionUserMessageParam(
    role="user",
    content=(
        'Сгенерируй ровно 5 вопросов, чтобы понять мои киновкусы. '
        'Ответь строго в формате JSON, без лишнего текста: '
        '[{"question": "Текст вопроса", "suggestions": ["Вариант 1", "Вариант 2"]}, ...]'
    )
)


USER_PROMPT_QUESTIONS_EN = ChatCompletionUserMessageParam(
    role="user",
    content=(
        'Generate exactly 5 questions to understand my movie preferences. '
        'Respond strictly in JSON format with no extra text: '
        '[{"question": "Question text", "suggestions": ["Option 1", "Option 2"]}, ...]'
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
        number_movies: int = PROMPT_NUM_MOVIES,
        lang: str = "ru"
) -> ChatCompletionUserMessageParam:

    query_styles = QUERY_STYLES_EN if lang == "en" else QUERY_STYLES_RU

    translated_genres = [GENRE_TRANSLATIONS.get(g, g) for g in genres] \
        if genres and lang == "en" else genres
    if translated_genres and ("any" in translated_genres or "любой" in translated_genres):
        translated_genres = []

    translated_atmospheres = [ATMOSPHERE_TRANSLATIONS.get(a, a) for a in atmospheres] \
        if atmospheres and lang == "en" else atmospheres
    if translated_atmospheres and ("any" in translated_atmospheres or "любой" in translated_atmospheres):
        translated_atmospheres = []

    user_prompt_parts = [
        f"Recommend {number_movies} already released movies" if lang == "en"
        else f"Посоветуй {number_movies} уже вышедших фильмов"
    ]

    if translated_genres:
        user_prompt_parts.append(
            f"Preferred genres: {', '.join(translated_genres)}" if lang == "en"
            else f"Желаемые жанры: {', '.join(translated_genres)}"
        )
    if translated_atmospheres:
        user_prompt_parts.append(
            f"Atmosphere: {', '.join(translated_atmospheres)}" if lang == "en"
            else f"Атмосфера: {', '.join(translated_atmospheres)}"
        )
    if start_year and end_year:
        user_prompt_parts.append(
            f"Released between {start_year} and {end_year}" if lang == "en"
            else f"Дата выхода между {start_year} и {end_year}"
        )
    if description:
        user_prompt_parts.append(
            f"User described it like this: {description}" if lang == "en"
            else f"Пользователь описал свой запрос так: {description}"
        )
    if suggestion:
        user_prompt_parts.append(
            f"In the spirit of the movie: {suggestion} (do not suggest it)" if lang == "en"
            else f"В духе фильма: {suggestion} (его самого не предлагай)"
        )

    user_prompt_parts.append(random.choice(query_styles))

    if favorites:
        user_prompt_parts.append(
            f"⚠️ Do not include favorites: {', '.join(favorites)}" if lang == "en"
            else f"⚠️ Не включай фильмы из избранного: {', '.join(favorites)}"
        )
    if exclude:
        user_prompt_parts.append(
            f"⚠️ Strictly exclude: {', '.join(exclude)}" if lang == "en"
            else f"⚠️ Строго исключи: {', '.join(exclude)}"
        )

    suffix = (
        '. Respond in JSON: '
        '{"movies": [{"title_alt": "Only the original-language movie title, no year"}]}' if lang == "en"
        else '. Ответь в формате JSON: '
             '{"movies": [{"title_alt": "Только название фильма на языке оригинала без указания года выпуска"}]}'
    )

    return ChatCompletionUserMessageParam(role="user", content=", ".join(user_prompt_parts) + suffix)


def build_user_prompt_chat(
        chat_answers: Optional[List[ChatQA]] = None,
        exclude: Optional[List[str]] = None,
        favorites: Optional[List[str]] = None,
        number_movies: int = PROMPT_NUM_MOVIES,
        lang: str = "ru"
) -> ChatCompletionUserMessageParam:
    query_styles = QUERY_STYLES_EN if lang == "en" else QUERY_STYLES_RU
    user_lines = [f"answer_{idx}: {chat.answer}" for idx, chat in enumerate(chat_answers, start=1)]
    content = ", ".join(user_lines) + ", " + random.choice(query_styles)

    if favorites:
        content += f" ⚠️ Do not include favorites: {', '.join(favorites)}" if lang == "en" \
            else f" ⚠️ Не включай избранные: {', '.join(favorites)}"
    if exclude:
        content += f" ⚠️ Strictly exclude: {', '.join(exclude)}" if lang == "en" \
            else f" ⚠️ Строго исключи: {', '.join(exclude)}"

    suffix = (
        f" Recommend {number_movies} already released movies. Respond in JSON: "
        '{"movies": [{"title_alt": "Only the original-language movie title, no year"}]}' if lang == "en"
        else f" Посоветуй {number_movies} уже вышедших фильмов. Ответь в формате JSON: "
             '{"movies": [{"title_alt": "Только название фильма на языке оригинала без указания года выпуска"}]}'
    )

    return ChatCompletionUserMessageParam(role="user", content=content + suffix)


def build_assistant_prompt(chat_answers: List[ChatQA]) -> ChatCompletionAssistantMessageParam:
    question_lines = [f"question_{idx}: {chat.question}" for idx, chat in enumerate(chat_answers, start=1)]
    content = ", ".join(question_lines) + ","

    return ChatCompletionAssistantMessageParam(
        role="assistant",
        content=content
    )