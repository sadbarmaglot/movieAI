from pydantic import BaseModel
from typing import List, Optional


class ChatQA(BaseModel):
    question: Optional[str] = None
    answer: str


class QuestionStreamingRequest(BaseModel):
    user_id: int


class MovieStreamingRequest(BaseModel):
    user_id: int
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
            tmdb_id=movie_data.get("externalId", {}).get("tmdb"),
            title_alt=movie_data.get("alternativeName", ""),
            title_ru=movie_data.get("name", ""),
            overview=movie_data.get("description", ""),
            rating_kp=movie_data.get("rating", {}).get("kp"),
            rating_imdb=movie_data.get("rating", {}).get("imdb"),
            movie_length=movie_data.get("movieLength", 0) or 0,
            genres=movie_data.get("genres", []),
            countries=movie_data.get("countries", []),
            **extras
        )


class MovieResponse(BaseModel):
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
