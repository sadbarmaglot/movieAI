from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db import FavoriteManager, MovieManager, UserManager

def get_session(request: Request) -> AsyncSession:
    return request.state.session


def get_user_manager(
    session: AsyncSession = Depends(get_session),
) -> UserManager:
    return UserManager(session)


def get_movie_manager(
    session: AsyncSession = Depends(get_session),
) -> MovieManager:
    return MovieManager(session)


def get_favorite_manager(
    session: AsyncSession = Depends(get_session),
) -> FavoriteManager:
    return FavoriteManager(session)