import logging

from typing import List, Dict, Union
from fastapi import HTTPException
from sqlalchemy import select, insert

from db_managers.base import (
    BaseManager,
    movies,
    skipped_movies,
    ios_skipped_movies,
    favorite_movies,
    ios_favorite_movies,
    read_only,
    transactional
)
from models import MovieResponse, MovieDetails


logger = logging.getLogger(__name__)


class MovieManager(BaseManager):

    @read_only
    async def get_by_kp_id(self, kp_id: int) -> MovieResponse:
        query = (
            select(
                movies.c.kp_id,
                movies.c.title_alt,
                movies.c.title_ru,
                movies.c.overview,
                movies.c.year,
                movies.c.google_cloud_url,
                movies.c.rating_kp,
                movies.c.rating_imdb,
                movies.c.movie_length,
                movies.c.genres,
                movies.c.countries,
                movies.c.background_color,
            )
            .where(movies.c.kp_id == kp_id) # type: ignore
        )

        result = await self.session.execute(query)
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Фильм не найден")

        return MovieResponse(
            movie_id=row.kp_id,
            title_alt=row.title_alt,
            title_ru=row.title_ru,
            overview=row.overview,
            poster_url=row.google_cloud_url,
            year=row.year,
            rating_kp=row.rating_kp,
            rating_imdb=row.rating_imdb,
            movie_length=row.movie_length,
            genres=row.genres,
            countries=row.countries,
            background_color=row.background_color,
        )

    @read_only
    async def get_by_title_gpt(self, title_gpt: str) -> Dict:
        query = select(
            movies.c.kp_id,
            movies.c.title_alt,
            movies.c.title_ru,
            movies.c.overview,
            movies.c.year,
            movies.c.google_cloud_url,
            movies.c.rating_kp,
            movies.c.rating_imdb,
            movies.c.movie_length,
            movies.c.genres,
            movies.c.countries,
            movies.c.background_color
        ).where(movies.c.title_alt == title_gpt) # type: ignore

        result = await self.session.execute(query)
        row = result.fetchone()

        if row:
            return {
                "movie_id": row.kp_id,
                "title_alt": row.title_alt,
                "title_ru": row.title_ru,
                "overview": row.overview,
                "year": row.year,
                "poster_url": row.google_cloud_url,
                "rating_kp": float(row.rating_kp) if row.rating_kp is not None else None,
                "rating_imdb": float(row.rating_imdb) if row.rating_imdb is not None else None,
                "movie_length": int(row.movie_length) if row.movie_length is not None else None,
                "genres": row.genres,
                "countries": row.countries,
                "background_color": row.background_color or "",
            }

        return {}

    @transactional
    async def insert_movies(self, movies_data: List[MovieDetails]) -> None:
        """
        Асинхронно вставляет новые строки в таблицу movies.
        :param movies_data: список объектов MovieDetails с данными фильмов
        """
        for movie_data in movies_data:
            query = select(movies.c.background_color).where(movies.c.kp_id == movie_data.kp_id) # type: ignore
            result = await self.session.execute(query)
            existing = result.mappings().first()

            if existing:
                if movie_data.background_color is None:
                    movie_data.background_color = existing.get("background_color")
            else:
                await self.session.execute(insert(movies).values(**movie_data.model_dump()))
                logger.info("✅ Фильм %s добавлен в БД", movie_data.title_alt)

    @transactional
    async def add_skipped_movies(self, user_id: Union[int, str], kp_id: int, platform: str = "telegram") -> None:
        """
        Асинхронно вставляет новые строки в таблицу skipped_movies.
        :param user_id: ID пользователя (int для Telegram) или device_id (str для iOS)
        :param kp_id: ID фильма на Кинопоиске
        :param platform: 'telegram' or 'ios'
        """
        # Выбираем таблицу в зависимости от платформы
        if platform == "ios":
            skipped_table = ios_skipped_movies
            user_field = ios_skipped_movies.c.device_id
            user_id_value = str(user_id)
            values = {"device_id": user_id_value, "kp_id": kp_id}
        else:
            skipped_table = skipped_movies
            user_field = skipped_movies.c.user_id
            user_id_value = int(user_id) if isinstance(user_id, str) else user_id
            values = {"user_id": user_id_value, "kp_id": kp_id}
        
        result = await self.session.execute(
            select(skipped_table).where(
                (user_field == user_id_value) &  # type: ignore
                (skipped_table.c.kp_id == kp_id)  # type: ignore
            )
        )
        exists = result.scalar_one_or_none()
        if not exists:
            await self.session.execute(
                insert(skipped_table).values(**values)
            )
            logger.info(f"{kp_id} was skipped")

    @read_only
    async def get_skipped(self, user_id: Union[int, str], platform: str = "telegram") -> List[int]:
        """Получает список пропущенных фильмов"""
        if platform == "ios":
            skipped_table = ios_skipped_movies
            user_field = ios_skipped_movies.c.device_id
            user_id_value = str(user_id)
        else:
            skipped_table = skipped_movies
            user_field = skipped_movies.c.user_id
            user_id_value = int(user_id) if isinstance(user_id, str) else user_id
        
        result = await self.session.execute(
            select(skipped_table).where(user_field == user_id_value) # type: ignore
        )
        rows = result.fetchall()
        return [row.kp_id for row in rows]

    @read_only
    async def get_favorites(self, user_id: Union[int, str], platform: str = "telegram") -> List[int]:
        """Получает список избранных фильмов (только kp_id)"""
        if platform == "ios":
            favorites_table = ios_favorite_movies
            user_field = ios_favorite_movies.c.device_id
            user_id_value = str(user_id)
        else:
            favorites_table = favorite_movies
            user_field = favorite_movies.c.user_id
            user_id_value = int(user_id) if isinstance(user_id, str) else user_id
        
        result = await self.session.execute(
            select(favorites_table).where(user_field == user_id_value) # type: ignore
        )
        rows = result.fetchall()
        return [row.kp_id for row in rows]