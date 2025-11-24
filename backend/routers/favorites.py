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
    request: Request,
    favorite_manager: FavoriteManager = Depends(get_favorite_manager),
    movie_manager: MovieManager = Depends(get_movie_manager)
):
    # Для iOS: убеждаемся, что фильм есть в ios_movies
    if body.platform == "ios":
        exists = await movie_manager.check_ios_movie_exists(body.movie_id)
        if not exists:
            # Получаем данные из Weaviate
            recommender = request.app.state.recommender
            weaviate_movie = await recommender.get_movie_by_kp_id(body.movie_id)
            if weaviate_movie:
                await movie_manager.ensure_ios_movie_from_weaviate(weaviate_movie)
                logger.info(f"[add_favorite] Фильм kp_id={body.movie_id} добавлен в ios_movies из Weaviate")
            else:
                logger.warning(f"[add_favorite] Фильм kp_id={body.movie_id} не найден в Weaviate, пропускаем добавление в ios_movies")
    
    await favorite_manager.add_favorite(
        user_id=body.user_id, 
        kp_id=body.movie_id, 
        platform=body.platform
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
