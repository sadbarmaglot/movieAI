"""
API endpoint for reddit-monitor: movie recommendations without auth/user context.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel, Field

from clients.weaviate_client import MovieWeaviateRecommender

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reddit", tags=["Reddit"])


class RedditRecommendRequest(BaseModel):
    query: Optional[str] = Field(None, description="Semantic search query, e.g. 'dark atmospheric sci-fi'")
    movie_name: Optional[str] = Field(None, description="Reference movie title for 'similar to X' searches")
    genres: Optional[List[str]] = Field(None, description="Genre filter, e.g. ['Science Fiction', 'Thriller']")
    start_year: int = Field(1900, description="Min release year")
    end_year: int = Field(2026, description="Max release year")
    exclude_titles: Optional[List[str]] = Field(None, description="Movie titles to exclude (already recommended in comments)")
    limit: int = Field(5, ge=1, le=20, description="Number of movies to return")
    locale: str = Field("en", description="Locale: 'en' or 'ru'")


class RedditMovieResult(BaseModel):
    title: str
    title_en: str
    year: Optional[int]
    rating_imdb: Optional[float]
    rating_kp: Optional[float]
    genres: List[str]
    overview: str


class RedditRecommendResponse(BaseModel):
    movies: List[RedditMovieResult]


@router.post("/recommend", response_model=RedditRecommendResponse)
async def reddit_recommend(body: RedditRecommendRequest, request: Request):
    """
    Returns movie recommendations for reddit-monitor.
    No auth, no user context — just query + filters → Weaviate results.
    """
    recommender: MovieWeaviateRecommender = request.app.state.recommender

    # Resolve exclude_titles to kp_ids
    exclude_kp_ids = set()
    if body.exclude_titles:
        for title in body.exclude_titles:
            found = await recommender.find_movies_by_title(
                title=title, locale=body.locale, min_score=3.0
            )
            if found:
                kp_id = found[0].get("kp_id")
                if kp_id:
                    exclude_kp_ids.add(kp_id)

    movies = await recommender.recommend(
        query=body.query,
        movie_name=body.movie_name,
        genres=body.genres,
        start_year=body.start_year,
        end_year=body.end_year,
        exclude_kp_ids=exclude_kp_ids or None,
        locale=body.locale,
    )

    results = []
    for movie in movies[:body.limit]:
        if body.locale == "en":
            title = movie.get("title") or movie.get("name") or ""
            overview = movie.get("overview") or movie.get("description") or ""
            genres = movie.get("genres_tmdb") or movie.get("genres") or []
        else:
            title = movie.get("name") or movie.get("title") or ""
            overview = movie.get("description") or movie.get("overview") or ""
            genres = movie.get("genres") or movie.get("genres_tmdb") or []

        results.append(RedditMovieResult(
            title=title,
            title_en=movie.get("title") or "",
            year=movie.get("year"),
            rating_imdb=movie.get("rating_imdb"),
            rating_kp=movie.get("rating_kp"),
            genres=genres,
            overview=overview,
        ))

    return RedditRecommendResponse(movies=results)
