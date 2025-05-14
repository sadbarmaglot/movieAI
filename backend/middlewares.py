from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from bot_app import check_telegram_signature
from db.base import AsyncSessionFactory
from settings import (
    API_KEY_NAME,
    API_KEY,
    INIT_DATA_HEADER_NAME,
    EXCLUDED_AUTH_PATHS,
    EXCLUDED_DBSESSION_PATHS
)


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

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Unauthorized request"}
        )


class DBSessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(path) for path in EXCLUDED_DBSESSION_PATHS):
            return await call_next(request)

        async with AsyncSessionFactory() as session:
            request.state.session = session
            response = await call_next(request)
            return response
