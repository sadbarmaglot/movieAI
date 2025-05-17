import logging

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from bot_app import check_telegram_signature
from settings import (
    API_KEY_NAME,
    API_KEY,
    INIT_DATA_HEADER_NAME,
    EXCLUDED_AUTH_PATHS,
)

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self,
                 app,
                 api_key: str = API_KEY,
                 init_data_header: str = INIT_DATA_HEADER_NAME,
                 api_key_header: str = API_KEY_NAME,
                 ):
        super().__init__(app)
        self.api_key = api_key
        self.init_data_header = init_data_header
        self.api_key_header = api_key_header

    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(path) for path in EXCLUDED_AUTH_PATHS):
            return await call_next(request)

        init_data = request.headers.get(self.init_data_header)
        api_key = request.headers.get(self.api_key_header)

        if (init_data and check_telegram_signature(init_data)) or (api_key and api_key == self.api_key):
            return await call_next(request)
        else:
            logger.warning("Unauthorized request: %s", request.url)

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Unauthorized request"}
        )