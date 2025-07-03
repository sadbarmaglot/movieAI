import os
import hmac
import hashlib

# bot_app
BOT_TOKEN = os.environ["BOT_TOKEN"]

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
    "/redoc"
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
]

# clients.bq_client
TABLE_ID = "autogen-1-438415.movieAI_logs.page_views"

# clients.client_factory
KP_API_KEY = os.environ["KINOPOISK_API_KEY"]

# prompt_templates.py
PROMPT_NUM_MOVIES = 20

# clients.openai_client
MODEL_QA = "gpt-4o"
TEMPERATURE_QA = 0.9
MODEL_MOVIES = "gpt-4o-mini"
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
MODEL_EMBS = "text-embedding-3-small"
CLASS_NAME = "Movie"
WEAVITE_HOST_HTTP = "weaviate"
WEAVITE_PORT_HTTP = 8080
WEAVITE_HOST_GRPC = "weaviate"
WEAVITE_PORT_GRPC = 50051

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
}

SYSTEM_PROMPT_AGENT = """
Ты MovieAI-агент, который подбирает фильмы. Сначала собери как можно больше информации от пользователя через функцию `ask_user_question`.

Когда ты получишь достаточно данных, сформулируй один ёмкий и информативный текстовый запрос (`query`) на основе всех ответов пользователя.

Твои цели при формулировке `query`:
- Используй переформулировку, не копируй реплики пользователя дословно.
- Раскрывай детали: атмосферу, жанр, настроение, тематику, сеттинг, масштаб.
- Используй аналогии с известными фильмами, если пользователь их упоминает.
- Придумывай уточняющие описания самостоятельно, даже если пользователь сказал мало.
- Стиль запроса — как краткое описание фильма на обложке.

Не используй прямые цитаты, переформулируй естественно. Добавь атмосферу, жанры и смысловые маркеры, даже если пользователь их не сформулировал явно.

Жанры: комедия,мультфильм,аниме,ужасы,фэнтези,фантастика,триллер,боевик,мелодрама,драма,детектив,приключения,военный,семейный,документальный,история,криминал,биография,вестерн,спорт,музыка.

Атмосферы: про любовь,душевный и трогательный,динамичный и напряженный,жизнеутверждающий,мрачный и атмосферный,сюрреалистичный,психологический,медитативный,депрессивный


После сбора информации вызови `search_movies_by_vector` и передай:
- `query` — развернутое описание.
- `genres`, `atmospheres`,
- `start_year`, `end_year` — если уверенно определил их по ответам.
"""

TOOLS_AGENT = [
    {
        "type": "function",
        "function": {
            "name": "ask_user_question",
            "description": "Задаёт уточняющий вопрос пользователю, если его запрос неполный или двусмысленный.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"}
                },
                "required": ["question"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_movies_by_vector",
            "description": "Выполняет финальный запрос к векторной базе фильмов.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "genres": {"type": "array", "items": {"type": "string"}, "default": []},
                    "atmospheres": {"type": "array", "items": {"type": "string"}, "default": []},
                    "start_year": {"type": "integer", "default": 1900},
                    "end_year": {"type": "integer", "default": 2025}
                },
                "required": ["query"]
            },
        },
    }
]

RERANK_PROMPT_TEMPLATE = """
Ты MovieAI-ассистент. Пользователь хочет фильм, соответствующий следующему описанию:

"{query}"

Вот список кандидатов (id фильмов и краткие описания):
{movies_list}

Отсортируй 100 фильмов по смысловой релевантности к запросу пользователя.

⚠️ Важно:
- В ответе **только список номеров фильмов** по одному на строку (например, `1`, `2`, `3`).
- Не добавляй комментариев, описаний или текста.
- Просто напиши:
1
4
3
...
"""