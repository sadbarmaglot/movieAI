from pydantic import BaseModel
from typing import List, Optional


class AddFavoriteRequest(BaseModel):
    user_id: int
    movie_id: int


class GetFavoriteResponse(BaseModel):
    order_id: Optional[int] = None
    is_watched: Optional[bool] = None
    movie_id: int
    title_alt: str
    title_ru: str
    overview: str
    poster_url: Optional[str] = ""
    year: Optional[int] = None
    rating_kp: Optional[float] = None
    rating_imdb: Optional[float] = None
    movie_length: Optional[int] = None
    genres: Optional[List[dict]] = None
    countries: Optional[List[dict]] = None
    background_color: Optional[str]


class DeleteFavoriteRequest(BaseModel):
    user_id: int
    movie_id: int


class WatchFavoriteRequest(BaseModel):
    user_id: int
    movie_id: int
    is_watched: bool