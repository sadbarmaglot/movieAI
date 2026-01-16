import hmac
import hashlib
import logging
import time

from collections import defaultdict

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from urllib.parse import parse_qs, unquote

from settings import (
    API_KEY_NAME,
    API_KEY,
    INIT_DATA_HEADER_NAME,
    EXCLUDED_AUTH_PATHS,
    TELEGRAM_INIT_DATA_SECRET,
)


logger = logging.getLogger(__name__)

# Паттерны путей, которые явно указывают на ботов/сканнеров
BOT_PATH_PATTERNS = [
    ".env",
    "phpinfo",
    "phpunit",
    "eval-stdin",
    "config.json",
    "config.js",
    "parameters.yml",
    "robots.txt",
    "sitemap.xml",
    "favicon.ico",
    ".git",
    ".DS_Store",
    "wp-",
    "administrator",
    "admin",
    "login",
    "owa",
    "Autodiscover",
    "version",
    "containers",
    "actuator",
    "SDK",
    "cgi-bin",
    ".well-known",
    "security.txt",
    "vendor/",
    "backup/",
    "debug/",
    "profiler/",
    "geoserver",
    "RDWeb",
    "wsman",
    "dana-",
    "sslvpn",
    "sonicos",
    "phoenix",
    "interface/root",
    "+CSCOL",
    "+CSCOE",
]


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self,
                 app,
                 api_key: str = API_KEY,
                 init_data_header: str = INIT_DATA_HEADER_NAME,
                 api_key_header: str = API_KEY_NAME,
                 init_data_secret: bytes = TELEGRAM_INIT_DATA_SECRET
                 ):
        super().__init__(app)
        self.api_key = api_key
        self.init_data_header = init_data_header
        self.api_key_header = api_key_header
        self.init_data_secret = init_data_secret
        # Rate limiting для логирования: IP -> последнее время логирования
        self._log_timestamps = defaultdict(float)
        # Интервал между логами для одного IP (в секундах)
        self._log_interval = 60  # 1 минута

    def _check_telegram_signature(self, init_data):
        parsed_data = parse_qs(init_data)
        hash_received = parsed_data.pop("hash", [""])[0].strip()
        if not hash_received:
            return False
        data_check_string = "\n".join(
            f"{key}={unquote(value[0])}" for key, value in sorted(parsed_data.items())
        )
        computed_hash = hmac.new(self.init_data_secret, data_check_string.encode(), hashlib.sha256).hexdigest()
        return computed_hash == hash_received

    def _is_bot_request(self, path: str) -> bool:
        """Проверяет, является ли запрос очевидным ботом/сканнером"""
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in BOT_PATH_PATTERNS)

    def _should_log(self, client_ip: str) -> bool:
        """Проверяет, нужно ли логировать запрос (rate limiting)"""
        current_time = time.time()
        last_log_time = self._log_timestamps.get(client_ip, 0)
        
        if current_time - last_log_time >= self._log_interval:
            self._log_timestamps[client_ip] = current_time
            # Очистка старых записей (старше 1 часа)
            if len(self._log_timestamps) > 1000:
                cutoff_time = current_time - 3600
                self._log_timestamps = {
                    ip: ts for ip, ts in self._log_timestamps.items()
                    if ts > cutoff_time
                }
            return True
        return False

    def _get_client_ip(self, request: Request) -> str:
        """Получает IP клиента из заголовков или прямого подключения"""
        # Проверяем заголовки прокси
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Прямое подключение
        if request.client:
            return request.client.host
        
        return "unknown"

    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(path) for path in EXCLUDED_AUTH_PATHS):
            return await call_next(request)

        init_data = request.headers.get(self.init_data_header)
        api_key = request.headers.get(self.api_key_header)

        if (init_data and self._check_telegram_signature(init_data)) or (api_key and api_key == self.api_key):
            return await call_next(request)
        else:
            if self._is_bot_request(request.url.path):
                logger.debug("Unauthorized bot/scanner request: %s", request.url)
            else:
                client_ip = self._get_client_ip(request)
                if self._should_log(client_ip):
                    logger.warning("Unauthorized request: %s [IP: %s]", request.url, client_ip)

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Unauthorized request"}
        )