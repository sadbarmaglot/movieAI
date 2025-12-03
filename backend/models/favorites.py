from pydantic import BaseModel
from typing import List, Optional, Union


class AddFavoriteRequest(BaseModel):
    user_id: Union[int, str]  # int для Telegram, str (device_id) для iOS
    movie_id: int
    platform: Optional[str] = "telegram"  # 'telegram' or 'ios'
    is_watched: Optional[bool] = False


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
    user_id: Union[int, str]  # int для Telegram, str (device_id) для iOS
    movie_id: int
    platform: Optional[str] = "telegram"  # 'telegram' or 'ios'


class WatchFavoriteRequest(BaseModel):
    user_id: Union[int, str]  # int для Telegram, str (device_id) для iOS
    movie_id: int
    is_watched: bool
    platform: Optional[str] = "telegram"  # 'telegram' or 'ios'