import re
import asyncio

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from clients import kp_client, openai_client
from clients.weaviate_client import MovieWeaviateRecommender
from db_managers import MovieManager
from models import (
    MovieDetails,
    MovieResponse,
    MovieStreamingRequest,
    QuestionStreamingRequest,
    WeaviateStreamingRequest
)
from routers.dependencies import get_session, get_movie_manager
from routers.auth import check_user_stars
from settings import ATMOSPHERE_MAPPING

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

@router.get("/weaviate-search-movies", response_model=List[MovieResponse])
async def search_movies(
    request: Request,
    movie_name: str
):
    recommender: MovieWeaviateRecommender = request.app.state.recommender

    results = recommender.search(query=movie_name)
    kp_ids = [r["kp_id"] for r in results]

    async def get_or_fetch_movie(kp_id: int) -> Optional[MovieDetails]:
        session = request.state.session_factory()
        movie_manager = MovieManager(session)
        try:
            movie = await movie_manager.get_by_kp_id(kp_id)
            return MovieDetails(
                kp_id=movie.movie_id,
                title_alt=movie.title_alt,
                title_ru=movie.title_ru,
                overview=movie.overview,
                poster_url=movie.poster_url,
                year=movie.year,
                rating_kp=movie.rating_kp,
                rating_imdb=movie.rating_imdb,
                movie_length=movie.movie_length,
                genres=movie.genres,
                countries=movie.countries,
                google_cloud_url=movie.poster_url,
                background_color=movie.background_color,
            )
        except HTTPException:
            return await kp_client.get_by_kp_id(kp_id)
        finally:
            await session.close()

    movies: List[Optional[MovieDetails]] = await asyncio.gather(
        *(get_or_fetch_movie(kp_id) for kp_id in kp_ids)
    )

    movies = [m for m in movies if m is not None]

    session = request.state.session_factory()
    try:
        movie_manager = MovieManager(session)
        await movie_manager.insert_movies(movies)
    finally:
        await session.close()

    return [MovieResponse.from_details(m) for m in movies]

@router.post("/questions-streaming")
async def questions_streaming(
    body: QuestionStreamingRequest,
    session: AsyncSession = Depends(get_session),
):
    await check_user_stars(session, user_id=body.user_id)
    return await openai_client.stream_questions()

@router.post("/weaviate-streaming")
async def weaviate_streaming(
    request: Request,
    body: WeaviateStreamingRequest,
    # session: AsyncSession = Depends(get_session),
):
    # await check_user_stars(session, user_id=body.user_id)
    recommender: MovieWeaviateRecommender = request.app.state.recommender

    if "любой" in body.atmospheres:
        query = None
    else:
        query = ",".join([ATMOSPHERE_MAPPING[atmosphere] for atmosphere in body.atmospheres])

    if "любой" in body.genres:
        genres = None
    else:
        genres = body.genres

    return await recommender.stream_movies_from_vector_search(
        user_id=body.user_id,
        query=query,
        genres=genres,
        start_year=body.start_year,
        end_year=body.end_year,
        exclude=body.exclude,
        favorites=body.favorites
    )


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
