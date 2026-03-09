"""
API endpoints для SEO-лендинга
"""
import asyncio
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Request, HTTPException, status
from openai import AsyncOpenAI
from pydantic import BaseModel

from clients.weaviate_client import MovieWeaviateRecommender
from settings import RERANK_PROMPT_TEMPLATE_RU, RERANK_PROMPT_TEMPLATE_EN, MODEL_RERANK

logger = logging.getLogger(__name__)

router = APIRouter()


async def _rerank_movies(
    openai_client: AsyncOpenAI,
    query: str,
    movies: List[dict],
    locale: str = "ru",
    source_movie_name: str | None = None,
) -> List[dict]:
    """Реранк фильмов через OpenAI (не-стриминговый, для лендинга)."""
    if not movies:
        return movies

    # Форматируем список фильмов
    lines = []
    for i, m in enumerate(movies):
        name = m.get("name") or m.get("title") or ""
        desc = (m.get("page_content") or "")[:200]
        lines.append(f"{i + 1}. [{name}] {desc}")
    movies_list = "\n".join(lines)

    # Exclude instruction
    exclude_instruction = ""
    if source_movie_name:
        if locale == "en":
            exclude_instruction = f"\n⚠️ EXCLUDE the movie \"{source_movie_name}\" itself from the ranking."
        else:
            exclude_instruction = f"\n⚠️ ИСКЛЮЧИ сам фильм \"{source_movie_name}\" из ранжирования."

    template = RERANK_PROMPT_TEMPLATE_EN if locale == "en" else RERANK_PROMPT_TEMPLATE_RU
    prompt = template.format(
        query=query,
        movies_list=movies_list,
        movies_count=len(movies),
        exclude_instruction=exclude_instruction,
        criteria_context="",
    )

    system_content = (
        "You are a movie recommendation assistant." if locale == "en"
        else "Ты помощник по подбору фильмов."
    )

    try:
        response = await asyncio.wait_for(
            openai_client.chat.completions.create(
                model=MODEL_RERANK,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt},
                ],
            ),
            timeout=30,
        )

        content = response.choices[0].message.content or ""
        reranked = []
        seen = set()
        for line in content.strip().split("\n"):
            match = re.match(r"(\d+)", line.strip())
            if match:
                idx = int(match.group(1)) - 1
                if 0 <= idx < len(movies) and idx not in seen:
                    seen.add(idx)
                    reranked.append(movies[idx])

        # Дополняем фильмами, которые реранк не вернул
        if len(reranked) < len(movies):
            reranked_kp_ids = {m.get("kp_id") for m in reranked}
            remaining = [m for m in movies if m.get("kp_id") not in reranked_kp_ids]
            reranked.extend(remaining)

        logger.info(f"[Landing] Rerank: {len(reranked)} фильмов отсортировано")
        return reranked

    except Exception as e:
        logger.error(f"[Landing] Ошибка rerank: {e}, возвращаем исходный порядок")
        return movies


class SimilarMoviesResponse(BaseModel):
    """Модель ответа для похожих фильмов на лендинге"""
    source_movie: dict  # Исходный фильм
    similar_movies: List[dict]  # Список похожих фильмов (5-8 штук)


@router.get("/landing/movies-like/{movie_slug}", response_model=SimilarMoviesResponse)
async def get_movies_like(
    request: Request,
    movie_slug: str,
    locale: str = "ru",
    limit: int = 9,
    kp_id: Optional[int] = None
):
    """
    Получает похожие фильмы для SEO-лендинга.
    
    Args:
        movie_slug: Slug названия фильма (например, "the-matrix" или "matrica")
        locale: Локализация ('ru' or 'en')
        limit: Количество похожих фильмов (по умолчанию 9, максимум 9)
        kp_id: Опциональный kp_id фильма. Если указан, используется напрямую без поиска по названию
    
    Returns:
        SimilarMoviesResponse с исходным фильмом и списком похожих
    """
    try:
        # Ограничиваем limit
        limit = min(limit, 9)
        
        recommender: MovieWeaviateRecommender = request.app.state.recommender
        source_kp_id = None
        source_movie = None
        
        # Если передан kp_id напрямую - используем его
        if kp_id:
            logger.info(
                f"[Landing] Используем переданный kp_id={kp_id} для slug='{movie_slug}'"
            )
            source_kp_id = kp_id
            
            # Получаем данные фильма по kp_id
            movie_data = await recommender.get_movie_by_kp_id(kp_id)
            if not movie_data:
                logger.warning(
                    f"[Landing] Фильм с kp_id={kp_id} не найден в базе"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Фильм с ID {kp_id} не найден"
                )
            source_movie = movie_data
        else:
            # Ищем фильм по названию (старая логика)
            movie_name = movie_slug.replace("-", " ").strip()
            
            logger.info(
                f"[Landing] Поиск похожих фильмов для: slug='{movie_slug}', "
                f"movie_name='{movie_name}', locale={locale}, limit={limit}"
            )
            
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

        # Определяем название фильма для лога и реранка
        movie_title_for_log = source_movie.get("name") or source_movie.get("title") or movie_slug

        # Реранк через OpenAI
        openai_client: AsyncOpenAI = request.app.state.openai_client
        query = f"фильмы похожие на {movie_title_for_log}" if locale == "ru" else f"movies similar to {movie_title_for_log}"
        similar_movies = await _rerank_movies(
            openai_client=openai_client,
            query=query,
            movies=similar_movies,
            locale=locale,
            source_movie_name=movie_title_for_log,
        )

        # Ограничиваем количество результатов
        similar_movies = similar_movies[:limit]

        logger.info(
            f"[Landing] Найдено {len(similar_movies)} похожих фильмов для '{movie_title_for_log}' (kp_id={source_kp_id})"
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

