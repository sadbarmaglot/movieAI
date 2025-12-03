from typing import List, Union
import logging

from fastapi import APIRouter, Depends, Request

from db_managers import FavoriteManager, MovieManager
from models import (
    GetFavoriteResponse,
    MovieResponseLocalized,
    AddFavoriteRequest,
    DeleteFavoriteRequest,
    WatchFavoriteRequest
)
from routers.dependencies import get_favorite_manager, get_movie_manager

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/get-favorites", response_model=Union[List[GetFavoriteResponse], List[MovieResponseLocalized]])
async def get_favorites_movies(
    user_id: Union[int, str],  # int для Telegram, str (device_id) для iOS
    platform: str = "telegram",
    favorite_manager: FavoriteManager = Depends(get_favorite_manager)
):
    """
    Получает избранные фильмы пользователя.
    Для Telegram возвращает List[GetFavoriteResponse].
    Для iOS возвращает List[MovieResponseLocalized] с данными для обеих локализаций.
    """
    return await favorite_manager.get_favorites(user_id=user_id, platform=platform)

@router.post("/add-favorites")
async def add_favorite_movie(
    body: AddFavoriteRequest,
    favorite_manager: FavoriteManager = Depends(get_favorite_manager),
):
    await favorite_manager.add_favorite(
        user_id=body.user_id, 
        kp_id=body.movie_id, 
        platform=body.platform,
        is_watched=body.is_watched or False
    )

@router.post("/delete-favorites")
async def delete_favorite_movie(
    body: DeleteFavoriteRequest,
    favorite_manager: FavoriteManager = Depends(get_favorite_manager)
):
    await favorite_manager.remove_favorite(
        user_id=body.user_id, 
        kp_id=body.movie_id,
        platform=body.platform
    )

@router.post("/watch-favorites")
async def watch_favorite_movie(
    body: WatchFavoriteRequest,
    favorite_manager: FavoriteManager = Depends(get_favorite_manager)
):
    await favorite_manager.mark_watched(
        user_id=body.user_id, 
        kp_id=body.movie_id, 
        is_watched=body.is_watched,
        platform=body.platform
    )
