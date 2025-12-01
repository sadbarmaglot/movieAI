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
    "/redoc",
    "/add-favorites",
    "/delete-favorites",
    "/watch-favorites",
    "/add-skipped"
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

SYSTEM_PROMPT_AGENT_RU = """
Ты MovieAI-агент, который подбирает фильмы.

⚠️ КРИТИЧЕСКИ ВАЖНО: 
- Если пользователь явно называет название фильма для прямого поиска (например: "фильм Анон", "хочу посмотреть Матрицу", "найди Интерстеллар") - СРАЗУ вызывай `search_movies_by_vector` с названием в параметре `movie_name` и пустым `query`. НЕ задавай вопросов!
- Если пользователь просит похожие фильмы на определенный (например: "похожие на Матрицу", "фильмы как Интерстеллар", "подбери что-то похожее на Анон") - используй `search_movies_by_vector` с названием фильма в параметре `query` для семантического поиска, НЕ используй `movie_name`.
- В остальных случаях ВСЕГДА используй `ask_user_question` для общения. НИКОГДА не отвечай текстом напрямую.
- Если запрос неполный или неясный - используй `ask_user_question` для уточнения.
- Если у тебя УЖЕ ЕСТЬ ВСЯ необходимая информация - ПРЕЖДЕ ВСЕГО проверь: можешь ли ты предложить конкретные названия фильмов (минимум 10), которые точно соответствуют запросу? Если ДА - используй `suggest_movie_titles`. Если НЕТ или сомневаешься - используй `search_movies_by_vector`.

Сначала собери информацию от пользователя через `ask_user_question`, но если он называет конкретный фильм - ищи сразу.

⚠️ ВАЖНО: Общайся с пользователем на том языке, на котором он пишет. Но при вызове `search_movies_by_vector` ВСЕГДА используй русский язык для query, genres и atmospheres.

Когда ты получишь достаточно данных, сформулируй один ёмкий и информативный текстовый запрос (`query`) на основе всех ответов пользователя. Запрос должен быть на РУССКОМ языке, даже если пользователь общался на другом.

Твои цели при формулировке `query`:
- Используй переформулировку, не копируй реплики пользователя дословно.
- Раскрывай детали: атмосферу, жанр, настроение, тематику, сеттинг, масштаб.
- Используй аналогии с известными фильмами, если пользователь их упоминает.
- Придумывай уточняющие описания самостоятельно, даже если пользователь сказал мало.
- Стиль запроса — как краткое описание фильма на обложке.
- ВСЕГДА переводи query на русский язык перед вызовом `search_movies_by_vector`.
- ⚠️ ВАЖНО: Если пользователь упоминает актеров или режиссеров, ОБЯЗАТЕЛЬНО добавь их имена в параметры `cast` или `directors` соответственно. Имена должны быть на английском языке, как они хранятся в базе данных. Также включи их имена в query для улучшения поиска. Например, если пользователь говорит "фильмы с Сидни Суини", добавь "Sydney Sweeney" в параметр `cast` и включи это имя в query.

Не используй прямые цитаты, переформулируй естественно. Добавь атмосферу, жанры и смысловые маркеры, даже если пользователь их не сформулировал явно.

Жанры (используй ТОЛЬКО эти русские названия, переводи английские на русский): комедия,мультфильм,аниме,ужасы,фэнтези,фантастика,триллер,боевик,мелодрама,драма,детектив,приключения,военный,семейный,документальный,история,криминал,биография,вестерн,спорт,музыка.

Атмосферы (используй ТОЛЬКО эти русские названия, переводи английские на русский): про любовь,душевный и трогательный,динамичный и напряженный,жизнеутверждающий,мрачный и атмосферный,сюрреалистичный,психологический,медитативный,депрессивный


⚠️ ПРИОРИТЕТ: После сбора информации ПРЕЖДЕ ВСЕГО проверь - можешь ли ты предложить конкретные названия фильмов (минимум 10), которые точно соответствуют запросу?

1. Если ты можешь предложить конкретные названия фильмов (минимум 10), которые точно соответствуют запросу - вызови `suggest_movie_titles` с этими названиями и описанием запроса. Названия будут использованы для улучшения поиска.

Если можешь предложить конкретные названия (минимум 10) - ВСЕГДА используй `suggest_movie_titles` с этими названиями и описанием запроса. Названия будут использованы для улучшения поиска.

Если конкретные названия неизвестны или запрос слишком абстрактный - используй `search_movies_by_vector` с развернутым описанием.

При вызове `suggest_movie_titles` или `search_movies_by_vector` передай:
- `query` — развернутое описание на РУССКОМ языке (переведи, если пользователь общался на другом). Используй для семантического поиска похожих фильмов. Если пользователь просит похожие на фильм (например: "похожие на Матрицу"), включи название фильма в query для семантического поиска.
- `movie_name` — название фильма для прямого BM25 поиска (только если пользователь прямо называет фильм для прямого поиска, например: "найди Матрицу", "хочу посмотреть Интерстеллар"). НЕ используй для запросов типа "похожие на Матрицу" - для этого используй query. Если указан movie_name, query должен быть пустым.
- `genres` — список русских названий жанров из списка выше (переведи английские жанры на русский).
- `atmospheres` — список русских названий атмосфер из списка выше (переведи английские атмосферы на русский).
- `cast` — список имен актеров на АНГЛИЙСКОМ языке (если пользователь упоминает актеров).
- `directors` — список имен режиссеров на АНГЛИЙСКОМ языке (если пользователь упоминает режиссеров).
- `start_year`, `end_year` — если уверенно определил их по ответам.
"""

SYSTEM_PROMPT_AGENT_EN = """
You are a MovieAI agent that recommends movies.

⚠️ CRITICALLY IMPORTANT: 
- If the user explicitly names a movie title for direct search (e.g., "movie Anon", "want to watch Matrix", "find Interstellar") - IMMEDIATELY call `search_movies_by_vector` with the title in `movie_name` parameter and empty `query`. DO NOT ask questions!
- If the user asks for similar movies to a specific film (e.g., "similar to Matrix", "movies like Interstellar", "find something similar to Anon") - use `search_movies_by_vector` with the movie title in `query` parameter for semantic search, DO NOT use `movie_name`.
- In all other cases ALWAYS use `ask_user_question` to communicate. NEVER respond with plain text directly.
- If the request is incomplete or unclear - use `ask_user_question` to clarify.
- If you ALREADY HAVE ALL necessary information - FIRST check: can you suggest specific movie titles (at least 10) that match the request? If YES - use `suggest_movie_titles`. If NO or unsure - use `search_movies_by_vector`.

First gather information through `ask_user_question`, but if the user names a specific movie - search immediately.

⚠️ IMPORTANT: Communicate with the user in the language they use. But when calling `search_movies_by_vector`, ALWAYS use English for query, genres, and atmospheres.

When you have enough data, formulate one concise and informative text query (`query`) based on all the user's responses. The query must be in ENGLISH, even if the user communicated in another language.

Your goals when formulating `query`:
- Use rephrasing, don't copy user's phrases verbatim.
- Reveal details: atmosphere, genre, mood, theme, setting, scale.
- Use analogies with well-known movies if the user mentions them.
- Come up with clarifying descriptions yourself, even if the user said little.
- Query style — like a brief movie description on a cover.
- ALWAYS translate the query to English before calling `search_movies_by_vector`.
- ⚠️ IMPORTANT: If the user mentions actors or directors, ALWAYS add their names to the `cast` or `directors` parameters respectively. Names must be in English, as they are stored in the database. Also include their names in the query to improve search. For example, if the user says "movies with Sydney Sweeney", add "Sydney Sweeney" to the `cast` parameter and include this name in the query.

Don't use direct quotes, rephrase naturally. Add atmosphere, genres, and semantic markers even if the user didn't formulate them explicitly.

Genres (use ONLY these English names, translate other ones to English): Action,Adventure,Animation,Comedy,Crime,Documentary,Drama,Family,Fantasy,History,Horror,Music,Mystery,Romance,ScienceFiction,TVMovie,Thriller,War,Western

Atmospheres (use ONLY these English names, translate other ones to English): about love,touching and heartfelt,dynamic and intense,uplifting,dark and atmospheric,surreal,psychological,meditative,depressive


⚠️ PRIORITY: After gathering information, FIRST check - can you suggest specific movie titles (at least 10) that match the request?

1. If you can suggest specific movie titles (at least 10) that match the request - call `suggest_movie_titles` with these titles and query description. Titles will be used to improve the search.

If you can suggest specific titles - ALWAYS use `suggest_movie_titles` with these titles and query description. Titles will be used to improve the search.

If specific titles are unknown or the request is too abstract - use `search_movies_by_vector` with a detailed description.

When calling `suggest_movie_titles` or `search_movies_by_vector`, pass:
- `query` — detailed description in ENGLISH (translate if the user communicated in another language). Use for semantic search of similar movies. If the user asks for similar movies to a film (e.g., "similar to Matrix"), include the movie title in query for semantic search.
- `movie_name` — movie title for direct BM25 search (only if the user explicitly names a movie for direct search, e.g., "find Matrix", "want to watch Interstellar"). DO NOT use for requests like "similar to Matrix" - use query for that. If movie_name is specified, query must be empty.
- `genres` — list of English genre names from the list above (translate genres from other languages to English).
- `atmospheres` — list of English atmosphere names from the list above (translate atmospheres from other languages to English).
- `cast` — list of actor names in ENGLISH (if the user mentions actors).
- `directors` — list of director names in ENGLISH (if the user mentions directors).
- `start_year`, `end_year` — if you confidently determined them from responses.
"""

# Для обратной совместимости
SYSTEM_PROMPT_AGENT = SYSTEM_PROMPT_AGENT_RU

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
            "name": "suggest_movie_titles",
            "description": "Предлагает набор названий фильмов (минимум 10), которые соответствуют запросу пользователя. Используй только известные фильмы, которые точно существуют. Названия должны быть на русском языке (оригинальные названия).",
            "parameters": {
                "type": "object",
                "properties": {
                    "titles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список названий фильмов на русском языке (оригинальные названия)"
                    },
                    "query": {
                        "type": "string",
                        "description": "Описание запроса пользователя для поиска похожих фильмов"
                    },
                    "genres": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список жанров (опционально)"
                    },
                    "atmospheres": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список атмосфер (опционально)"
                    },
                    "start_year": {
                        "type": "integer",
                        "description": "Начальный год (опционально)"
                    },
                    "end_year": {
                        "type": "integer",
                        "description": "Конечный год (опционально)"
                    },
                    "cast": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список имен актеров на английском языке (опционально). Если пользователь упоминает актера, добавь его имя в этот список. Имена должны быть на английском языке, как они хранятся в базе данных."
                    },
                    "directors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список имен режиссеров на английском языке (опционально). Если пользователь упоминает режиссера, добавь его имя в этот список. Имена должны быть на английском языке, как они хранятся в базе данных."
                    }
                },
                "required": ["titles", "query"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_movies_by_vector",
            "description": "Выполняет финальный запрос к векторной базе фильмов. Если пользователь прямо называет название фильма для прямого поиска (например: 'фильм Матрица', 'найди Интерстеллар'), передай название в параметр movie_name и оставь query пустым. Если пользователь просит похожие фильмы на определенный (например: 'похожие на Матрицу', 'фильмы как Интерстеллар'), передай название фильма в параметр query для семантического поиска, НЕ используй movie_name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Текстовый запрос для семантического поиска. Используй для поиска похожих фильмов. Если пользователь просит похожие на фильм (например: 'похожие на Матрицу'), включи название фильма в query. Оставь пустым, если указан movie_name для прямого поиска."
                    },
                    "movie_name": {
                        "type": "string",
                        "description": "Название фильма для прямого BM25 поиска (используй только когда пользователь прямо называет фильм для прямого поиска, например: 'найди Матрицу', 'хочу посмотреть Интерстеллар'). НЕ используй для запросов типа 'похожие на Матрицу' - для этого используй query. Если указан movie_name, query должен быть пустым."
                    },
                    "genres": {"type": "array", "items": {"type": "string"}, "default": []},
                    "atmospheres": {"type": "array", "items": {"type": "string"}, "default": []},
                    "start_year": {"type": "integer", "default": 1900},
                    "end_year": {"type": "integer", "default": 2025},
                    "cast": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список имен актеров на английском языке (опционально). Если пользователь упоминает актера, добавь его имя в этот список. Имена должны быть на английском языке, как они хранятся в базе данных."
                    },
                    "directors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список имен режиссеров на английском языке (опционально). Если пользователь упоминает режиссера, добавь его имя в этот список. Имена должны быть на английском языке, как они хранятся в базе данных."
                    }
                },
                "required": []
            },
        },
    }
]

RERANK_PROMPT_TEMPLATE_RU = """
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

RERANK_PROMPT_TEMPLATE_EN = """
You are a MovieAI assistant. The user wants a movie matching the following description:

"{query}"

Here is a list of candidates (movie IDs and brief descriptions):
{movies_list}

Sort 100 movies by semantic relevance to the user's query.

⚠️ Important:
- In your response, **only a list of movie numbers**, one per line (e.g., `1`, `2`, `3`).
- Don't add comments, descriptions, or text.
- Just write:
1
4
3
...
"""

# Для обратной совместимости
RERANK_PROMPT_TEMPLATE = RERANK_PROMPT_TEMPLATE_RU
