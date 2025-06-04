from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List

from clients.openai_client.rag_pipeline import MovieWeaviateRecommender

router = APIRouter()

class RecommendRequest(BaseModel):
    question: str
    year_from: int = 1990
    year_to: int = 2025
    genres: List[str]
    rating_kp: float = 5.0
    rating_imdb: float = 5.0


@router.post("/recommend")
async def recommend_movies(request: Request, data: RecommendRequest):
    recommender: MovieWeaviateRecommender = request.app.state.recommender
    movies = recommender.recommend(
        query=data.question,
        year_from=data.year_from,
        year_to=data.year_to,
        genres=data.genres,
        rating_kp=data.rating_kp,
        rating_imdb=data.rating_imdb
    )
    return movies