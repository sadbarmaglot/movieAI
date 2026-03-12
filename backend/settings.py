import os
import hmac
import hashlib
from datetime import datetime

# bot_app
BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_FEEDBACK_TOKEN = os.environ["BOT_FEEDBACK_TOKEN"]

# bot_controller
WEB_APP_URL = os.environ["WEB_APP_URL"]
ADMIN_ID = 267429209
BUTTON_TEXT = {
    "ru": "Открыть мини-приложение",
    "en": "Open Mini App"
}
WELCOME_MESSAGE = {
    "ru": "🎬 *Добро пожаловать в MovieAI!*\n\n"
          "Подберите фильм по описанию, настроению или жанру — с помощью приложения.\n\n"
          "Отправьте /help, чтобы узнать обо всех возможностях.\n\n"
          "Нажмите кнопку ниже, чтобы начать.\n\n",
    "en" : "🎬 *Welcome to MovieAI!*\n\n"
           "Find a movie by description, mood, or genre — using the app.\n\n"
           "Send /help to learn all the features.\n\n"
           "Tap the button below to get started.\n\n"
}
HELP_MESSAGE = {
    "ru": "❓ *Что умеет MovieAI*\n\n"
          "Вы можете выбрать удобный способ поиска фильмов:\n"
          "•  По жанру, атмосфере, году и другим фильтрам\n"
          "•  По вашему описанию — в интерактивном чате\n"
          "•  По понравившемуся фильму — найдёт похожие\n\n"
          "❤️ В подборе — добавляйте фильмы в избранное, чтобы не потерять лучшие находки.\n\n"
          "У вас есть идея, вопрос или предложение? \nПросто напишите в сообщении боту — он всё читает!\n\n"
          "Нажмите /start, чтобы открыть мини-приложение\n\n",
    "en" : "❓ *What MovieAI can do*\n\n"
            "You can search for movies in a way that suits you:\n"
            "• By genre, atmosphere, year, and other filters\n"
            "• By your description — in an interactive chat\n"
            "• By similar movies — find more like the ones you like\n\n"
            "❤️ In matching — add movies to your favorites so you don’t lose great finds.\n\n"
            "Have an idea, question, or suggestion?\nJust send a message — we read everything!\n\n"
            "Tap /start to open the mini-app\n\n"
}
FEEDBACK_MASSAGE = {
    "ru": "Спасибо за обратную связь! Мы всё учтём 🙌",
    "en": "Thanks for the feedback! We'll take it into account 🙌"
}
PAYMENT_MESSAGE = {
    "ru": lambda amount: f"🎉 Платёж прошёл успешно! Тебе начислено {amount} звезд ⭐️",
    "en": lambda amount: f"🎉 Payment successful! You've received {amount} stars ⭐️"
}

# middlewares.auth_middleware
API_KEY = os.environ["API_KEY"]
API_KEY_NAME = "X-API-Key"
INIT_DATA_HEADER_NAME = "X-Telegram-Init-Data"
TELEGRAM_INIT_DATA_SECRET = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
EXCLUDED_AUTH_PATHS = {
    "/health",
    "/preview",
    "/docs",
    "/docs/oauth2-redirect",
    "/openapi.json",
    "/redoc",
    "/add-favorites",
    "/delete-favorites",
    "/watch-favorites",
    "/add-skipped",
    "/get-popular-movies",
    "/feedback",
    "/landing",
    "/reddit"
}

# middlewares.db_session_middleware
EXCLUDED_DBSESSION_PATHS = {
    "/health",
    "/log-event",
    "/docs",
    "/docs/oauth2-redirect",
    "/openapi.json",
    "/redoc"
}

# middlewares.logging_middleware
EXCLUDED_LOG_PATHS = ["/health",]

# main
ALLOW_ORIGINS = [
    "https://autogenz.com",
    "https://storage.googleapis.com",
    "http://localhost:5173",
    "https://movieaiapp.com"
]

# clients.bq_client
TABLE_ID = "autogen-1-438415.movieAI_logs.page_views"
SESSION_TABLE_ID = "autogen-1-438415.movieAI_logs.movie_sessions"

# clients.client_factory
KP_API_KEY = os.environ["KINOPOISK_API_KEY"]

# prompt_templates.py
PROMPT_NUM_MOVIES = 20

# clients.openai_client
MODEL_QA = "gpt-5.1"
TEMPERATURE_QA = 0.9
MODEL_MOVIES = "gpt-4o-mini"
MODEL_RERANK = "gpt-4o-mini"
TEMPERATURE_MOVIES = 0.9
QUESTION_PREFIX_PATTERN = r'\{\s*"questions"\s*:\s*\['
MOVIES_PREFIX_PATTERN = r'\{\s*"movies"\s*:\s*\['
OVERRIDE_DATA = {
    "The Witch": "The VVitch: A New-England Folktale",
    "Train to Busan": "Busanhaeng",
    "Train to Busan 2": "Bando",
    "The Platform": "El Hoyo",
    "The Platform 2": "El Hoyo 2",
    "The Red Turtle": "La tortue rouge",
    "Nymphomaniac": "Nymphomaniac: Vol. I"
}

# clients.gc_client
BUCKET_NAME = "autogen-images"

# db_managers.base
SQL_HOST=os.environ["SQL_HOST"]
SQL_PORT=os.environ["SQL_PORT"]
SQL_DB=os.environ["SQL_DB"]
SQL_USER=os.environ["SQL_USER"]
SQL_PSWRD = os.environ["SQL_PSWRD"]
ASYNC_DATABASE_URL = f"postgresql+asyncpg://{SQL_USER}:{SQL_PSWRD}@{SQL_HOST}:{SQL_PORT}/{SQL_USER}"

# clients.rag_pipeline
INDEX_PATH = os.environ["INDEX_PATH"]
TOP_K_FETCH = 5000
TOP_K_HYBRID = 1000
TOP_K_SIMILAR = 1000
TOP_K_SEARCH = 30
MODEL_EMBS = "text-embedding-3-large"
CLASS_NAME = "Movie"  # Коллекция с расширенными метаданными
WEAVIATE_HOST_HTTP = "weaviate"
WEAVIATE_PORT_HTTP = 8080
WEAVIATE_HOST_GRPC = "weaviate"
WEAVIATE_PORT_GRPC = 50051

# Локализация
DEFAULT_LOCALE = "ru"  # ru или en
SUPPORTED_LOCALES = ["ru", "en"]

ATMOSPHERE_MAPPING = {
    "про любовь" : "История о сильных чувствах, романтических отношениях, эмоциональной близости между героями. "
                   "Фильм с тёплой атмосферой, трогательными моментами, драмой или лёгкой комедией, "
                   "в центре которой — любовь, страсть или судьбоносная встреча.",
    "душевный и трогательный" : "Добрые, эмоциональные фильмы, вызывающие сочувствие и заставляющие переживать за героев. "
                                "Сюжет обычно связан с преодолением трудностей, силой семьи, дружбы или внутреннего роста. "
                                "Атмосфера мягкая, теплая, повествование неспешное и человечное.",
    "динамичный и напряженный" : "Интенсивные, захватывающие истории с быстрым развитием событий, экшеном, конфликтами "
                                 "и сильным напряжением. Часто присутствуют погони, опасность, сложные моральные выборы. "
                                 "Атмосфера тревожная и будоражащая.",
    "жизнеутверждающий" : "Фильм, вдохновляющий на надежду, веру в добро, преодоление трудностей. "
                          "Герои меняются к лучшему, находят силы жить, любить и прощать. "
                          "История часто построена на реальных событиях или важном личностном опыте. "
                          "Атмосфера светлая, мотивирующая, uplifting.",
    "мрачный и атмосферный" : "Сюжет с гнетущей, тёмной атмосферой, часто с элементами драмы, нуара, триллера или хоррора. "
                              "Визуальный стиль насыщен тенями, контрастами, медленным темпом. "
                              "История разворачивается в депрессивных, загадочных или опасных обстоятельствах.",
    "сюрреалистичный" : "Необычный, абстрактный фильм, где нарушаются законы логики и реальности. "
                        "Истории могут напоминать сны, галлюцинации или философские притчи. "
                        "Много символизма, необычного визуала, абсурдных сцен и двойных смыслов.",
    "психологический" : "Глубокий фильм, исследующий внутренний мир персонажей, их страхи, мотивации, травмы. "
                        "Часто построен на интриге, неожиданностях и напряжении. "
                        "Атмосфера плотная, часто тревожная или напряжённая. "
                        "Могут быть элементы триллера, драмы или детектива.",
    "медитативный" : "Спокойный, неспешный фильм, создающий атмосферу созерцания. "
                     "Мало диалогов, визуально насыщенные сцены, акцент на звуке, природе, времени. "
                     "История может быть минималистичной или вовсе отсутствовать. "
                     "Вдохновляют на размышления, ощущение здесь и сейчас.",
    "депрессивный" : "Мрачная и тяжёлая история, затрагивающая темы одиночества, утраты, бессмысленности жизни. "
                     "Часто присутствует психологическое напряжение, ощущение безысходности, холодная цветовая палитра. "
                     "История эмоционально сложная, трагичная.",
    # Английские ключи
    "about love": "A story about strong feelings, romantic relationships, emotional closeness between characters. "
                  "A film with a warm atmosphere, touching moments, drama or light comedy, "
                  "centered on love, passion, or a fateful meeting.",
    "touching and heartfelt": "Kind, emotional films that evoke empathy and make you worry about the characters. "
                             "The plot is usually related to overcoming difficulties, the strength of family, friendship, or inner growth. "
                             "The atmosphere is soft, warm, the narrative is unhurried and humane.",
    "dynamic and intense": "Intense, gripping stories with rapid plot development, action, conflicts "
                          "and strong tension. Often there are chases, danger, complex moral choices. "
                          "The atmosphere is anxious and exciting.",
    "uplifting": "A film that inspires hope, faith in goodness, overcoming difficulties. "
                 "Characters change for the better, find strength to live, love, and forgive. "
                 "The story is often based on real events or important personal experience. "
                 "The atmosphere is bright, motivating, uplifting.",
    "dark and atmospheric": "A plot with an oppressive, dark atmosphere, often with elements of drama, noir, thriller, or horror. "
                            "Visual style is rich in shadows, contrasts, slow pace. "
                            "The story unfolds in depressive, mysterious, or dangerous circumstances.",
    "surreal": "An unusual, abstract film where the laws of logic and reality are violated. "
               "Stories may resemble dreams, hallucinations, or philosophical parables. "
               "Lots of symbolism, unusual visuals, absurd scenes, and double meanings.",
    "psychological": "A deep film exploring the inner world of characters, their fears, motivations, traumas. "
                     "Often built on intrigue, surprises, and tension. "
                     "The atmosphere is dense, often anxious or tense. "
                     "May have elements of thriller, drama, or mystery.",
    "meditative": "A calm, unhurried film creating an atmosphere of contemplation. "
                  "Few dialogues, visually rich scenes, emphasis on sound, nature, time. "
                  "The story may be minimalistic or absent altogether. "
                  "Inspires reflection, a sense of here and now.",
    "depressive": "A gloomy and heavy story touching on themes of loneliness, loss, meaninglessness of life. "
                  "Often there is psychological tension, a sense of hopelessness, a cold color palette. "
                  "The story is emotionally complex, tragic.",
}

CURRENT_YEAR = datetime.now().year
LAST_YEAR = CURRENT_YEAR - 1

SYSTEM_PROMPT_AGENT_RU = f"""
Ты MovieAI-агент, который подбирает фильмы.

📅 Сейчас {CURRENT_YEAR} год. "Прошлый год" = {LAST_YEAR}, "этот год" = {CURRENT_YEAR}.

🚫 Ты помогаешь ТОЛЬКО с подбором фильмов. На нерелевантные вопросы используй `ask_user_question`, чтобы вернуть разговор к фильмам.

ПРАВИЛА:
- Пользователь называет конкретный фильм → сразу `search_movies_by_vector` с `movie_name`. НЕ задавай вопросов.
- "Похожие на [фильм]" / "типа [фильма]" → `movie_name` + `query` с описанием атмосферы/жанра фильма. Пример: "похожие на Матрицу" → movie_name="Матрица", query="научная фантастика, виртуальная реальность, экшен, киберпанк".
- "Фильмы [фамилия]" = запрос режиссера/актера → используй `search_movies_by_vector` с `directors`/`cast`, БЕЗ `query` и БЕЗ `movie_name`. Бэкенд найдет фильмы по метаданным, query только мешает.
- Сериалы — в базе ТОЛЬКО фильмы. Используй `query` с описанием стиля/атмосферы сериала.
- В остальных случаях используй `ask_user_question` с 3-5 короткими suggestions. Никогда не отвечай текстом напрямую.

ЯЗЫК:
- Общайся на ТОМ ЖЕ языке, на котором пишет пользователь. Если язык неясен или неоднозначен, отвечай на русском.
- При вызове `search_movies_by_vector` или `suggest_movie_titles` — query, genres, atmospheres ВСЕГДА на русском.

ФОРМУЛИРОВКА QUERY:
- Переформулируй естественно, не копируй дословно. Раскрывай атмосферу, настроение, тематику.
- Стиль — как краткое описание фильма на обложке.

ЖАНРЫ (ТОЛЬКО эти русские названия): комедия, мультфильм, аниме, ужасы, фэнтези, фантастика, триллер, боевик, мелодрама, драма, детектив, приключения, военный, семейный, документальный, история, криминал, биография, вестерн, спорт, музыка.

АТМОСФЕРЫ (ТОЛЬКО эти): про любовь, душевный и трогательный, динамичный и напряженный, жизнеутверждающий, мрачный и атмосферный, сюрреалистичный, психологический, медитативный, депрессивный

ВЫБОР ИНСТРУМЕНТА:
- Запрос по актёру/режиссёру → ВСЕГДА `search_movies_by_vector` с `cast`/`directors`. НЕ используй `suggest_movie_titles`.
- Если можешь предложить минимум 10 конкретных релевантных названий → `suggest_movie_titles` (названия на РУССКОМ).
- Иначе → `search_movies_by_vector` с развернутым описанием.

GENRES: передавай жанры, которые пользователь явно назвал или которые однозначно следуют из описания. НЕ додумывай жанры при запросе по актёру/режиссёру без указания жанра (например, "фильмы с Киану Ривзом" → genres=[]). Бэкенд использует contains_all с fallback на основной жанр. Подтип жанра ("черная комедия") → основной жанр в genres + подтип в query.

ГОДЫ: извлекай из диалога. "Прошлый год" → {LAST_YEAR}. Конкретные даты → start_year/end_year. Если не указано → не фильтруй (1900-{CURRENT_YEAR}).
"""

SYSTEM_PROMPT_AGENT_EN = f"""
You are a MovieAI agent that recommends movies.

📅 Current year: {CURRENT_YEAR}. "Last year" = {LAST_YEAR}, "this year" = {CURRENT_YEAR}.

🚫 You help ONLY with movie recommendations. For unrelated questions, use `ask_user_question` to redirect back to movies.

RULES:
- User names a specific movie → immediately `search_movies_by_vector` with `movie_name`. Do NOT ask questions.
- "Similar to [movie]" / "like [movie]" → `movie_name` + `query` with atmosphere/genre description. Example: "similar to Matrix" → movie_name="Matrix", query="sci-fi, virtual reality, action, cyberpunk".
- "Movies by [surname]" = director/actor request → use `search_movies_by_vector` with `directors`/`cast`, WITHOUT `query` and WITHOUT `movie_name`. The backend finds movies by metadata, query only interferes.
- TV series — the database has ONLY movies. Use `query` with a description of the series' style/atmosphere.
- Otherwise use `ask_user_question` with 3-5 short suggestions. Never respond with plain text.

LANGUAGE:
- Respond in the SAME language the user writes in. If the language is unclear or ambiguous, default to English.
- When calling `search_movies_by_vector` or `suggest_movie_titles` — query, genres, atmospheres ALWAYS in English.

QUERY FORMULATION:
- Rephrase naturally, don't copy verbatim. Reveal atmosphere, mood, theme.
- Style — like a brief movie description on a cover.

GENRES (ONLY these English names): Action, Adventure, Animation, Comedy, Crime, Documentary, Drama, Family, Fantasy, History, Horror, Music, Mystery, Romance, Science Fiction, TVMovie, Thriller, War, Western

ATMOSPHERES (ONLY these): about love, touching and heartfelt, dynamic and intense, uplifting, dark and atmospheric, surreal, psychological, meditative, depressive

TOOL CHOICE:
- Actor/director request → ALWAYS `search_movies_by_vector` with `cast`/`directors`. Do NOT use `suggest_movie_titles`.
- If you can suggest at least 10 specific relevant titles → `suggest_movie_titles` (titles in ENGLISH).
- Otherwise → `search_movies_by_vector` with a detailed description.

GENRES: pass genres the user explicitly mentioned or that clearly follow from their description. Do NOT infer genres for actor/director requests without a genre mentioned (e.g., "movies with Keanu Reeves" → genres=[]). The backend uses contains_all with fallback to primary genre. Genre subtype ("black comedy") → main genre in genres + subtype in query.

YEARS: extract from dialogue. "Last year" → {LAST_YEAR}. Specific dates → start_year/end_year. If not mentioned → don't filter (1900-{CURRENT_YEAR}).
"""

SYSTEM_PROMPT_AGENT = SYSTEM_PROMPT_AGENT_RU  # default for __init__

# ---------------------------------------------------------------------------
# Tool descriptions by locale: (tool_name, param_name) → {locale: text}
# param_name=None → tool-level description
# ---------------------------------------------------------------------------
_TOOL_DESC = {
    # ── ask_user_question ──
    ("ask_user_question", None): {
        "ru": "Задаёт уточняющий вопрос пользователю, если его запрос неполный или двусмысленный. Рекомендуется предоставлять 3-5 предложенных вариантов ответов (suggestions) для удобства пользователя.",
        "en": "Asks a clarifying question to the user if their request is incomplete or ambiguous. It is recommended to provide 3-5 suggested answer options (suggestions) for user convenience.",
    },
    ("ask_user_question", "question"): {
        "ru": "Текст вопроса для пользователя",
        "en": "Question text for the user",
    },
    ("ask_user_question", "suggestions"): {
        "ru": "Опционально: 3-5 предложенных вариантов быстрых ответов для пользователя. Каждый вариант должен быть коротким (1-5 слов), релевантным вопросу и на том же языке, что и вопрос. Например, для вопроса о жанре: ['Боевик', 'Комедия', 'Драма', 'Триллер']",
        "en": "Optional: 3-5 suggested quick answer options for the user. Each option should be short (1-5 words), relevant to the question, and in the same language as the question. For example, for a genre question: ['Action', 'Comedy', 'Drama', 'Thriller']",
    },
    # ── suggest_movie_titles ──
    ("suggest_movie_titles", None): {
        "ru": "Предлагает набор названий фильмов (минимум 10), которые соответствуют запросу пользователя. Используй только известные фильмы, которые точно существуют. Названия должны быть на русском языке (оригинальные названия).",
        "en": "Suggests a set of movie titles (at least 10) that match the user's request. Use only well-known movies that definitely exist. Titles must be in ENGLISH (as they are stored in the database).",
    },
    ("suggest_movie_titles", "titles"): {
        "ru": "Список названий фильмов на русском языке (оригинальные названия)",
        "en": "List of movie titles in ENGLISH (as they are stored in the database)",
    },
    ("suggest_movie_titles", "query"): {
        "ru": "Описание запроса пользователя для поиска похожих фильмов",
        "en": "Description of the user's request for finding similar movies",
    },
    # ── search_movies_by_vector ──
    ("search_movies_by_vector", None): {
        "ru": "Выполняет финальный запрос к векторной базе фильмов. Два режима работы: (1) Прямой поиск фильма: пользователь называет конкретный фильм ('найди Матрицу') → передай movie_name, query оставь пустым. (2) Поиск похожих: пользователь хочет похожие фильмы ('похожие на Матрицу', 'что-то вроде Интерстеллара') → передай movie_name И query с описанием атмосферы/жанра. Система найдёт фильм по названию и вернёт похожие по вектору. ⚠️ НЕ используй movie_name для режиссёров/актёров ('фильмы Нолана') — используй directors/cast. ⚠️ НЕ используй movie_name для сериалов — в базе ТОЛЬКО фильмы, используй query с описанием стиля.",
        "en": "Executes a final query to the vector database of movies. Two modes: (1) Direct search: user names a specific movie ('find Matrix') → pass movie_name, leave query empty. (2) Similar search: user wants similar movies ('similar to Matrix', 'something like Interstellar') → pass movie_name AND query with atmosphere/genre description. The system will find the movie by title and return similar ones by vector. ⚠️ DO NOT use movie_name for directors/actors ('movies by Nolan') — use directors/cast. ⚠️ DO NOT use movie_name for TV series — database has ONLY movies, use query with style description.",
    },
    ("search_movies_by_vector", "query"): {
        "ru": "Текстовый запрос для семантического поиска. При поиске похожих фильмов (movie_name указан) — опиши атмосферу, жанр, тематику (например: 'научная фантастика, виртуальная реальность, киберпанк, экшен'). Оставь пустым при прямом поиске по movie_name.",
        "en": "Text query for semantic search. When searching for similar movies (movie_name is set) — describe atmosphere, genre, theme (e.g., 'sci-fi, virtual reality, cyberpunk, action'). Leave empty for direct movie_name search.",
    },
    ("search_movies_by_vector", "movie_name"): {
        "ru": "Название конкретного фильма. Используй когда пользователь: (1) ищет конкретный фильм ('найди Матрицу') → movie_name='Матрица', query пустой; (2) хочет похожие фильмы ('похожие на Матрицу', 'что-то типа Интерстеллара') → movie_name='Матрица', query='научная фантастика, виртуальная реальность, экшен'. ⚠️ НЕ используй для режиссёров/актёров ('фильмы нолана') — используй directors/cast. ⚠️ НЕ используй для сериалов — в базе ТОЛЬКО фильмы, используй query.",
        "en": "Specific movie title. Use when the user: (1) searches for a specific movie ('find Matrix') → movie_name='Matrix', query empty; (2) wants similar movies ('similar to Matrix', 'something like Interstellar') → movie_name='Matrix', query='sci-fi, virtual reality, action'. ⚠️ DO NOT use for directors/actors ('movies by Nolan') — use directors/cast. ⚠️ DO NOT use for TV series — database has ONLY movies, use query.",
    },
    # ── Shared params (same key used by both suggest_movie_titles and search_movies_by_vector) ──
    ("_shared", "genres"): {
        "ru": "Жанры из списка в системном промпте. Передавай жанры, которые пользователь явно назвал или которые однозначно следуют из описания. НЕ додумывай жанры при запросе по актёру/режиссёру. Например: для 'хоррор-комедия' передай ['ужасы', 'комедия']. Фильтр в базе данных.",
        "en": "Genres from the system prompt list. Pass genres the user explicitly mentioned or that clearly follow from their description. Do NOT infer genres for actor/director requests. For example: for 'horror comedy' pass ['Horror', 'Comedy']. Used as a database filter.",
    },
    ("_shared", "atmospheres"): {
        "ru": "Список атмосфер из списка в системном промпте.",
        "en": "List of atmospheres from the system prompt list.",
    },
    ("_shared", "start_year"): {
        "ru": "Начальный год (опционально)",
        "en": "Start year (optional)",
    },
    ("_shared", "end_year"): {
        "ru": "Конечный год (опционально)",
        "en": "End year (optional)",
    },
    ("_shared", "cast"): {
        "ru": "Список имен актеров на английском языке. ОБЯЗАТЕЛЬНО извлеки имена актеров из ВСЕГО контекста диалога (включая начальный запрос и все ответы пользователя), переведи русские имена на английские и добавь в этот список. Например: если пользователь упомянул 'Бенедикт Камбербэтч' или 'Камбербетч' в любом месте диалога, добавь ['Benedict Cumberbatch']. Имена должны быть на английском языке, как они хранятся в базе данных. НЕ оставляй пустым, если в диалоге упоминались актеры!",
        "en": "List of actor names in ENGLISH. ALWAYS extract actor names from the ENTIRE dialogue context (including the initial request and all user responses), translate non-English names to English, and add them to this list. For example: if the user mentioned 'Benedict Cumberbatch' or 'Камбербетч' anywhere in the dialogue, add ['Benedict Cumberbatch']. Names must be in ENGLISH, as they are stored in the database. DO NOT leave empty if actors were mentioned in the dialogue!",
    },
    ("_shared", "directors"): {
        "ru": "Список имен режиссеров на английском языке. ОБЯЗАТЕЛЬНО извлеки имена режиссеров из ВСЕГО контекста диалога (включая начальный запрос и все ответы пользователя), переведи русские имена на английские и добавь в этот список. Распознай известных режиссеров по фамилиям (например: 'Нолан' = 'Christopher Nolan', 'Тарантино' = 'Quentin Tarantino', 'Спилберг' = 'Steven Spielberg'). Имена должны быть на английском языке, как они хранятся в базе данных. НЕ оставляй пустым, если в диалоге упоминались режиссеры!",
        "en": "List of director names in ENGLISH. ALWAYS extract director names from the ENTIRE dialogue context (including the initial request and all user responses), translate non-English names to English, and add them to this list. Recognize famous directors by surnames (e.g., 'Nolan' = 'Christopher Nolan', 'Tarantino' = 'Quentin Tarantino', 'Spielberg' = 'Steven Spielberg'). Names must be in ENGLISH, as they are stored in the database. DO NOT leave empty if directors were mentioned in the dialogue!",
    },
    ("_shared", "rating_kp"): {
        "ru": "Минимальный рейтинг на Кинопоиске (от 0.0 до 10.0). Извлекай из диалога, если пользователь упоминает рейтинг Кинопоиска, 'высокий рейтинг', 'качественное кино' или конкретные числа (например: 'рейтинг выше 7', 'не ниже 8.5'). Если не указано явно, используй 0.0 (без фильтрации).",
        "en": "Minimum rating on Kinopoisk (from 0.0 to 10.0). Extract from dialogue if the user mentions Kinopoisk rating, 'high rating', 'quality movie' or specific numbers (e.g., 'rating above 7', 'not below 8.5'). If not explicitly specified, use 0.0 (no filtering).",
    },
    ("_shared", "rating_imdb"): {
        "ru": "Минимальный рейтинг на IMDb (от 0.0 до 10.0). Извлекай из диалога, если пользователь упоминает рейтинг IMDb, 'высокий рейтинг', 'качественное кино' или конкретные числа (например: 'IMDB выше 7', 'не ниже 8.5'). Если не указано явно, используй 0.0 (без фильтрации).",
        "en": "Minimum rating on IMDb (from 0.0 to 10.0). Extract from dialogue if the user mentions IMDb rating, 'high rating', 'quality movie' or specific numbers (e.g., 'IMDB above 7', 'not below 8.5'). If not explicitly specified, use 0.0 (no filtering).",
    },
}

# ---------------------------------------------------------------------------
# Tool structure (defined once, descriptions injected by get_agent_tools)
# ---------------------------------------------------------------------------
_TOOLS_STRUCTURE = [
    {
        "type": "function",
        "function": {
            "name": "ask_user_question",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "suggestions": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_movie_titles",
            "parameters": {
                "type": "object",
                "properties": {
                    "titles": {"type": "array", "items": {"type": "string"}},
                    "query": {"type": "string"},
                    "genres": {"type": "array", "items": {"type": "string"}},
                    "atmospheres": {"type": "array", "items": {"type": "string"}},
                    "start_year": {"type": "integer"},
                    "end_year": {"type": "integer"},
                    "cast": {"type": "array", "items": {"type": "string"}},
                    "directors": {"type": "array", "items": {"type": "string"}},
                    "rating_kp": {"type": "number"},
                    "rating_imdb": {"type": "number"},
                },
                "required": ["titles", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_movies_by_vector",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "movie_name": {"type": "string"},
                    "genres": {"type": "array", "items": {"type": "string"}, "default": []},
                    "atmospheres": {"type": "array", "items": {"type": "string"}, "default": []},
                    "start_year": {"type": "integer", "default": 1900},
                    "end_year": {"type": "integer", "default": CURRENT_YEAR},
                    "cast": {"type": "array", "items": {"type": "string"}},
                    "directors": {"type": "array", "items": {"type": "string"}},
                    "rating_kp": {"type": "number"},
                    "rating_imdb": {"type": "number"},
                },
                "required": [],
            },
        },
    },
]


def get_agent_tools(locale: str = "ru") -> list:
    """Build tools list with descriptions for the given locale."""
    import copy
    tools = copy.deepcopy(_TOOLS_STRUCTURE)
    for tool in tools:
        fn = tool["function"]
        name = fn["name"]
        fn["description"] = _TOOL_DESC[(name, None)][locale]
        for param, schema in fn["parameters"]["properties"].items():
            key = (name, param)
            if key not in _TOOL_DESC:
                key = ("_shared", param)
            if key in _TOOL_DESC:
                schema["description"] = _TOOL_DESC[key][locale]
    return tools


TOOLS_AGENT = get_agent_tools("ru")

RERANK_PROMPT_TEMPLATE_RU = """
Ты MovieAI-ассистент. Пользователь хочет фильм, соответствующий следующему описанию:

"{query}"
{criteria_context}
{exclude_instruction}

Вот список из {movies_count} кандидатов (номер, название, описание):
{movies_list}

Отсортируй ВСЕ {movies_count} фильмов по смысловой релевантности к запросу пользователя. Верни ВСЕ номера, не пропуская ни одного.

⚠️ Важно:
- В ответе **все {movies_count} номеров фильмов** по одному на строку.
- Не добавляй комментариев или текста.
"""

RERANK_PROMPT_TEMPLATE_EN = """
You are a MovieAI assistant. The user wants a movie matching the following description:

"{query}"
{criteria_context}
{exclude_instruction}

Here is a list of {movies_count} candidates (number, title, description):
{movies_list}

Sort ALL {movies_count} movies by semantic relevance to the user's query. Return ALL numbers, skip none.

⚠️ Important:
- In your response, **all {movies_count} movie numbers**, one per line.
- Don't add comments or text.
"""

# Для обратной совместимости
RERANK_PROMPT_TEMPLATE = RERANK_PROMPT_TEMPLATE_RU
