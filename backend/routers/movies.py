import re

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from clients import kp_client, openai_client
from db_managers import MovieManager
from models import (
    MovieResponse,
    MovieStreamingRequest,
    QuestionStreamingRequest
)
from routers.dependencies import get_session, get_movie_manager
from routers.auth import check_user_stars

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/search-movies", response_model=List[MovieResponse])
async def search_movies(
    movie_name: str,
    movie_manager: MovieManager = Depends(get_movie_manager),
):
    response = await kp_client.search(query=movie_name)
    await movie_manager.insert_movies(response)
    return [MovieResponse.from_details(m) for m in response]

@router.post("/questions-streaming")
async def questions_streaming(
    body: QuestionStreamingRequest,
    session: AsyncSession = Depends(get_session),
):
    await check_user_stars(session, user_id=body.user_id)
    return await openai_client.stream_questions()

@router.post("/movies-streaming")
async def movies_streaming(
    body: MovieStreamingRequest,
    session: AsyncSession = Depends(get_session),
):
    await check_user_stars(session, user_id=body.user_id)

    return await openai_client.stream_movies(
        user_id=body.user_id,
        chat_answers=body.chat_answers,
        genres=body.categories,
        atmospheres=body.atmospheres,
        description=body.description,
        suggestion=body.suggestion,
        start_year=body.start_year,
        end_year=body.end_year,
        exclude=body.exclude,
        favorites=body.favorites
    )

@router.get("/get-movie", response_model=MovieResponse)
async def get_movie(
        movie_id: int,
        movie_manager: MovieManager = Depends(get_movie_manager)
):
    return await movie_manager.get_by_kp_id(kp_id=movie_id)

@router.get("/preview/{params}", response_class=HTMLResponse)
async def preview_movie(
        request: Request,
        params: str,
        movie_manager: MovieManager = Depends(get_movie_manager)
):
    """
    Пример ожидаемого params: 'movie_123456_ref_789012'
    """
    match = re.match(r"movie_(\d+)(?:_ref_(\d+))?", params)
    if not match:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный формат ссылки.")
    movie_id = int(match.group(1))
    ref_user_id = int(match.group(2)) if match.group(2) else None
    movie_data = await movie_manager.get_by_kp_id(kp_id=movie_id)
    return templates.TemplateResponse("preview.html", {
        "request": request,
        "title": movie_data.title_ru,
        "description": movie_data.overview,
        "poster_url": movie_data.poster_url,
        "movie_id": movie_id,
        "ref_user_id": ref_user_id
    })
