"""
API endpoints для SEO-лендинга
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel

from clients.weaviate_client import MovieWeaviateRecommender

logger = logging.getLogger(__name__)

router = APIRouter()


class SimilarMoviesResponse(BaseModel):
    """Модель ответа для похожих фильмов на лендинге"""
    source_movie: dict  # Исходный фильм
    similar_movies: List[dict]  # Список похожих фильмов (5-8 штук)


@router.get("/landing/movies-like/{movie_slug}", response_model=SimilarMoviesResponse)
async def get_movies_like(
    request: Request,
    movie_slug: str,
    locale: str = "ru",
    limit: int = 8
):
    """
    Получает похожие фильмы для SEO-лендинга.
    
    Args:
        movie_slug: Slug названия фильма (например, "the-matrix" или "matrica")
        locale: Локализация ('ru' or 'en')
        limit: Количество похожих фильмов (по умолчанию 8, максимум 8)
    
    Returns:
        SimilarMoviesResponse с исходным фильмом и списком похожих
    """
    try:
        # Ограничиваем limit
        limit = min(limit, 8)
        
        # Преобразуем slug в название фильма (заменяем дефисы на пробелы)
        movie_name = movie_slug.replace("-", " ").strip()
        
        logger.info(
            f"[Landing] Поиск похожих фильмов для: slug='{movie_slug}', "
            f"movie_name='{movie_name}', locale={locale}, limit={limit}"
        )
        
        recommender: MovieWeaviateRecommender = request.app.state.recommender
        
        # Ищем фильм по названию
        movies_by_title = await recommender.find_movies_by_title(
            title=movie_name,
            locale=locale,
            min_score=0.5
        )
        
        if not movies_by_title:
            logger.warning(
                f"[Landing] Фильм '{movie_name}' не найден (slug: '{movie_slug}')"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Фильм '{movie_name}' не найден"
            )
        
        source_movie = movies_by_title[0]
        source_kp_id = source_movie.get("kp_id")
        
        if not source_kp_id:
            logger.warning(
                f"[Landing] Найденный фильм '{movie_name}' не имеет kp_id"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении данных фильма"
            )
        
        # Получаем похожие фильмы
        similar_movies = await recommender.recommend_similar(
            source_kp_id=source_kp_id,
            exclude_kp_ids=None  # На лендинге не исключаем фильмы
        )
        
        # Ограничиваем количество результатов
        similar_movies = similar_movies[:limit]
        
        logger.info(
            f"[Landing] Найдено {len(similar_movies)} похожих фильмов для '{movie_name}'"
        )
        
        return SimilarMoviesResponse(
            source_movie=source_movie,
            similar_movies=similar_movies
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Landing] Ошибка при получении похожих фильмов: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )

