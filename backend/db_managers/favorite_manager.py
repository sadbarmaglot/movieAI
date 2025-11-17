from typing import List
from sqlalchemy import select, insert, delete, update

from db_managers.base import (
    BaseManager,
    favorite_movies,
    ios_favorite_movies,
    movies,
    read_only,
    transactional
    )
from models import GetFavoriteResponse

class FavoriteManager(BaseManager):

    @read_only
    async def get_favorites(self, user_id: int, platform: str = "telegram") -> List[GetFavoriteResponse]:
        """
        Получает избранные фильмы пользователя.
        
        Args:
            user_id: ID пользователя (int для Telegram) или device_id (str для iOS)
            platform: 'telegram' or 'ios'
        """
        # Выбираем таблицу в зависимости от платформы
        if platform == "ios":
            favorites_table = ios_favorite_movies
            user_field = ios_favorite_movies.c.device_id
        else:
            favorites_table = favorite_movies
            user_field = favorite_movies.c.user_id
        
        favorites_subquery = (
            select(
                favorites_table.c.id,
                favorites_table.c.kp_id,
                favorites_table.c.iswatched
            ).where(user_field == user_id) # type: ignore
        ).subquery()

        query = (
            select(
                favorites_subquery.c.id,
                favorites_subquery.c.iswatched,
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
            .select_from(
                movies.join(favorites_subquery, favorites_subquery.c.kp_id == movies.c.kp_id)
            )
        )

        result = await self.session.execute(query)
        rows = result.fetchall()

        return [
            GetFavoriteResponse(
                order_id=row.id,
                is_watched=row.iswatched,
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
            ) for row in rows
        ]

    @transactional
    async def add_favorite(self, user_id, kp_id: int, platform: str = "telegram") -> None:
        """
        Добавляет фильм в избранное.
        
        Args:
            user_id: ID пользователя (int для Telegram) или device_id (str для iOS)
            kp_id: ID фильма на Кинопоиске
            platform: 'telegram' or 'ios'
        """
        # Выбираем таблицу в зависимости от платформы
        if platform == "ios":
            favorites_table = ios_favorite_movies
            user_field = ios_favorite_movies.c.device_id
            values = {"device_id": user_id, "kp_id": kp_id}
        else:
            favorites_table = favorite_movies
            user_field = favorite_movies.c.user_id
            values = {"user_id": user_id, "kp_id": kp_id}
        
        result = await self.session.execute(
            select(favorites_table).where(
                (user_field == user_id) & # type: ignore
                (favorites_table.c.kp_id == kp_id) # type: ignore
            )
        )
        exists = result.scalar_one_or_none()
        if not exists:
            await self.session.execute(
                insert(favorites_table).values(**values)
            )

    @transactional
    async def remove_favorite(self, user_id, kp_id: int, platform: str = "telegram") -> None:
        """Удаляет фильм из избранного"""
        if platform == "ios":
            favorites_table = ios_favorite_movies
            user_field = ios_favorite_movies.c.device_id
        else:
            favorites_table = favorite_movies
            user_field = favorite_movies.c.user_id
        
        await self.session.execute(
            delete(favorites_table).where(
                (user_field == user_id) & # type: ignore
                (favorites_table.c.kp_id == kp_id) # type: ignore
            )
        )

    @transactional
    async def mark_watched(self, user_id, kp_id: int, is_watched: bool, platform: str = "telegram") -> None:
        """Отмечает фильм как просмотренный/непросмотренный"""
        if platform == "ios":
            favorites_table = ios_favorite_movies
            user_field = ios_favorite_movies.c.device_id
        else:
            favorites_table = favorite_movies
            user_field = favorite_movies.c.user_id
        
        await self.session.execute(
            update(favorites_table)
            .where(
                (user_field == user_id) & # type: ignore
                (favorites_table.c.kp_id == kp_id) # type: ignore
            )
            .values(iswatched=is_watched)
        )
