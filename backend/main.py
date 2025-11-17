import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from middlewares import (
    AuthMiddleware,
    DBSessionMiddleware,
    LoggingMiddleware,
)
from clients.weaviate_client  import MovieWeaviateRecommender, load_vectorstore_weaviate

from clients.client_factory import kp_client, openai_client_base_async
from openapi_config import custom_openapi
from routers import health, favorites, movies, users
from settings import ALLOW_ORIGINS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    weaviate_client = load_vectorstore_weaviate()
    weaviate_client.connect()
    recommender = MovieWeaviateRecommender(
        weaviate_client=weaviate_client,
        openai_client=openai_client_base_async,
        kp_client=kp_client
    )
    logger.info("✅ MovieWeaviateRecommender initialized with Weaviate.")

    app.state.recommender = recommender
    app.state.openai_client = openai_client_base_async

    yield


def create_app() -> FastAPI:
    fastapi_app = FastAPI(lifespan=lifespan)
    fastapi_app.openapi = lambda: custom_openapi(fastapi_app)

    _configure_middleware(fastapi_app)
    _include_routers(fastapi_app)

    return fastapi_app


def _configure_middleware(fastapi_app: FastAPI) -> None:
    fastapi_app.add_middleware(LoggingMiddleware) # type: ignore
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
