from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from db_managers import AsyncSessionFactory
from settings import EXCLUDED_DBSESSION_PATHS


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