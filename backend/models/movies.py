from pydantic import BaseModel
from typing import List, Optional, TypedDict, Union


class ChatQA(BaseModel):
    question: Optional[str] = None
    answer: str


class QuestionStreamingRequest(BaseModel):
    user_id: Union[int, str]  # int для Telegram, str (device_id) для iOS
    platform: Optional[str] = "telegram"  # 'telegram' or 'ios'


class MovieStreamingRequest(BaseModel):
    user_id: Union[int, str]  # int для Telegram, str (device_id) для iOS
    platform: Optional[str] = "telegram"  # 'telegram' or 'ios'
    locale: Optional[str] = "ru"  # 'ru' or 'en' - локализация клиента
    chat_answers: List[ChatQA] = None
    categories: Optional[List[str]] = None
    atmospheres: Optional[List[str]] = None
    description: Optional[str] = ""
    suggestion: Optional[str] = ""
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    exclude: Optional[List[str]] = None
    favorites: Optional[List[str]] = None


class MovieDetails(BaseModel):
    """Базовая модель данных фильма для Telegram (старая схема)"""
    kp_id: int
    tmdb_id: Optional[int] = None
    title_gpt: str = ""
    title_alt: str
    title_ru: str
    overview: str
    poster_url: str
    year: int
    rating_kp: Optional[float] = None
    rating_imdb: Optional[float] = None
    movie_length: int = 0
    genres: List[dict] = []
    countries: List[dict] = []
    google_cloud_url: Optional[str] = None
    background_color: Optional[str] = None

    @classmethod
    def from_kp_data(cls, movie_data: dict, **extras) -> "MovieDetails":
        return cls(
            kp_id=movie_data["id"],
            tmdb_id=(movie_data.get("externalId") or {}).get("tmdb"),
            title_alt=movie_data.get("alternativeName") or "",
            title_ru=movie_data.get("name", ""),
            overview=movie_data.get("description", ""),
            rating_kp=movie_data.get("rating", {}).get("kp"),
            rating_imdb=movie_data.get("rating", {}).get("imdb"),
            movie_length=movie_data.get("movieLength", 0) or 0,
            genres=movie_data.get("genres", []),
            countries=movie_data.get("countries", []),
            **extras
        )


class MovieDetailsIOS(BaseModel):
    """Модель данных фильма для iOS с расширенными метаданными (Movie_v2 schema)"""
    # Основные идентификаторы
    kp_id: int
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    
    # Локализованные поля (русский)
    name: str  # название на русском
    description: str # описание на русском
    genres: List[dict] # жанры на русском
    countries: List[dict]  # страны на русском
    
    # Локализованные поля (английский)
    title: Optional[str] = None  # название на английском
    overview: Optional[str] = None  # описание на английском
    genres_tmdb: Optional[List[dict]] = None  # жанры на английском
    origin_country: Optional[List[dict]] = None  # страны на английском
    
    # Общие поля
    year: int
    movie_length: Optional[int] = None
    rating_kp: Optional[float] = None
    rating_imdb: Optional[float] = None
    popularity_score: Optional[float] = None
    
    # Метаданные
    cast: Optional[List[str]] = None  # актеры
    directors: Optional[List[str]] = None  # режиссеры
    keywords: Optional[List[str]] = None  # ключевые слова
    
    # Постеры и цвета фона
    kp_file_path: Optional[str] = None  # путь к постеру из Кинопоиска
    kp_background_color: Optional[str] = None  # цвет фона из Кинопоиска
    tmdb_file_path: Optional[str] = None  # путь к постеру из TMDB
    tmdb_background_color: Optional[str] = None  # цвет фона из TMDB


class MovieResponse(BaseModel):
    """Базовая модель ответа фильма (для обратной совместимости с Telegram)"""
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

    @classmethod
    def from_details(cls, movie: MovieDetails) -> "MovieResponse":
        return cls(
            movie_id=movie.kp_id,
            title_alt=movie.title_alt,
            title_ru=movie.title_ru,
            overview=movie.overview,
            poster_url=movie.google_cloud_url,
            year=movie.year,
            rating_kp=movie.rating_kp,
            rating_imdb=movie.rating_imdb,
            movie_length=movie.movie_length,
            genres=movie.genres,
            countries=movie.countries,
            background_color=movie.background_color,
        )


class MovieResponseLocalized(BaseModel):
    """Объединенная модель ответа фильма с данными для обеих локализаций (RU и EN)"""
    movie_id: int  # kp_id
    imdb_id: Optional[str] = None
    
    # Русская локализация
    name: Optional[str] = None  # название на русском
    overview_ru: Optional[str] = None  # описание на русском
    genres_ru: Optional[List[dict]] = None  # жанры на русском
    countries_ru: Optional[List[dict]] = None  # страны на русском
    poster_url_kp: Optional[str] = None  # постер из Кинопоиска
    background_color_kp: Optional[str] = None  # цвет фона из Кинопоиска
    
    # Английская локализация
    title: str  # название на английском
    overview_en: Optional[str] = None  # описание на английском
    genres_en: Optional[List[dict]] = None  # жанры на английском
    countries_en: Optional[List[dict]] = None  # страны на английском
    poster_url_tmdb: Optional[str] = None  # постер из TMDB
    background_color_tmdb: Optional[str] = None  # цвет фона из TMDB
    
    # Общие поля
    year: int
    rating_kp: Optional[float] = None
    rating_imdb: Optional[float] = None
    movie_length: Optional[int] = None



class AddSkippedRequest(BaseModel):
    user_id: Union[int, str]  # int для Telegram, str (device_id) для iOS
    movie_id: int
    platform: Optional[str] = "telegram"  # 'telegram' or 'ios'


class MovieObject(TypedDict):
    kp_id: int
    title_ru: str
    year: int
    genres: Optional[List[str]]
    rating_kp: float
    rating_imdb: float
    page_content: str


# Новая модель для Movie_v2 с расширенными метаданными
class MovieObjectV2(TypedDict, total=False):
    kp_id: int
    tmdb_id: Optional[int]
    imdb_id: Optional[str]
    name: Optional[str]  # название на русском
    title: Optional[str]  # название на английском
    year: int
    description: Optional[str]  # описание на русском
    overview: Optional[str]  # описание на английском
    movieLength: Optional[int]
    genres: Optional[List[str]]  # жанры на русском
    genres_tmdb: Optional[List[str]]  # жанры на английском
    countries: Optional[List[str]]  # страны на русском
    origin_country: Optional[List[str]]  # страны на английском
    cast: Optional[List[str]]
    directors: Optional[List[str]]
    keywords: Optional[List[str]]
    page_content: Optional[str]
    rating_kp: Optional[float]
    rating_imdb: Optional[float]
    kp_file_path: Optional[str]
    kp_background_color: Optional[str]
    tmdb_file_path: Optional[str]
    tmdb_background_color: Optional[str]
    popularity_score: Optional[float]