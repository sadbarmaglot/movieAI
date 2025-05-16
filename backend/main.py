from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from middlewares import AuthMiddleware, DBSessionMiddleware
from openapi_config import custom_openapi
from routers import health, favorites, movies, users
from settings import ALLOW_ORIGINS

def create_app() -> FastAPI:
    fastapi_app = FastAPI()
    fastapi_app.openapi = lambda: custom_openapi(fastapi_app)

    _configure_middleware(fastapi_app)
    _include_routers(fastapi_app)

    return fastapi_app

def _configure_middleware(fastapi_app: FastAPI) -> None:
    fastapi_app.add_middleware(AuthMiddleware) # type: ignore
    fastapi_app.add_middleware(DBSessionMiddleware) # type: ignore
    fastapi_app.add_middleware(
        CORSMiddleware, # type: ignore
        allow_origins=ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def _include_routers(fastapi_app: FastAPI) -> None:
    fastapi_app.include_router(health.router)
    fastapi_app.include_router(favorites.router, tags=["Favorites"])
    fastapi_app.include_router(movies.router, tags=["Movies"])
    fastapi_app.include_router(users.router, tags=["User"])

app = create_app()