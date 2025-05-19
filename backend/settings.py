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
SQL_PSWRD = os.environ["SQL_PSWRD"]
ASYNC_DATABASE_URL = f"postgresql+asyncpg://test:{SQL_PSWRD}@localhost/test"
