from typing import List

from fastapi import APIRouter, Depends

from db_managers import FavoriteManager
from models import (
    GetFavoriteResponse,
    AddFavoriteRequest,
    DeleteFavoriteRequest,
    WatchFavoriteRequest
)
from routers.dependencies import get_favorite_manager


router = APIRouter()

@router.get("/get-favorites", response_model=List[GetFavoriteResponse])
async def get_favorites_movies(
    user_id: int,
    favorite_manager: FavoriteManager = Depends(get_favorite_manager)
):
    return await favorite_manager.get_favorites(user_id=user_id)

@router.post("/add-favorites")
async def add_favorite_movie(
    body: AddFavoriteRequest,
    favorite_manager: FavoriteManager = Depends(get_favorite_manager)
):
    await favorite_manager.add_favorite(user_id=body.user_id, kp_id=body.movie_id)

@router.post("/delete-favorites")
async def delete_favorite_movie(
    body: DeleteFavoriteRequest,
    favorite_manager: FavoriteManager = Depends(get_favorite_manager)
):
    await favorite_manager.remove_favorite(user_id=body.user_id, kp_id=body.movie_id)

@router.post("/watch-favorites")
async def watch_favorite_movie(
    body: WatchFavoriteRequest,
    favorite_manager: FavoriteManager = Depends(get_favorite_manager)
):
    await favorite_manager.mark_watched(user_id=body.user_id, kp_id=body.movie_id, is_watched=body.is_watched)
