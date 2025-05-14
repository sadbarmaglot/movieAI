from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from middlewares import AuthMiddleware, DBSessionMiddleware
from openapi_config import custom_openapi
from routers import health, favorites, movies, users
from settings import ALLOW_ORIGINS
app = FastAPI()
app.openapi = lambda: custom_openapi(app)

# Middleware
app.add_middleware(AuthMiddleware)
app.add_middleware(DBSessionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(favorites.router, tags=["Favorites"])
app.include_router(movies.router, tags=["Movies"])
app.include_router(users.router, tags=["User"])
