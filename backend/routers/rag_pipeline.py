from fastapi import APIRouter, Request
from pydantic import BaseModel

from clients.openai_client.rag_pipeline import MovieRAGRecommender

router = APIRouter()

class RecommendRequest(BaseModel):
    question: str

@router.post("/recommend")
async def recommend_movies(request: Request, data: RecommendRequest):
    recommender: MovieRAGRecommender = request.app.state.recommender
    top_movies = recommender.recommend(question=data.question)
    return top_movies