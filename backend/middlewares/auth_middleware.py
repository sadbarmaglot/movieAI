import hmac
import hashlib
import logging

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

    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(path) for path in EXCLUDED_AUTH_PATHS):
            return await call_next(request)

        init_data = request.headers.get(self.init_data_header)
        api_key = request.headers.get(self.api_key_header)

        if (init_data and self._check_telegram_signature(init_data)) or (api_key and api_key == self.api_key):
            return await call_next(request)
        else:
            logger.warning("Unauthorized request: %s", request.url)

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Unauthorized request"}
        )