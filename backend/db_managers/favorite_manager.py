import logging
from typing import List, Union
from sqlalchemy import select, insert, delete, update

from db_managers.base import (
    BaseManager,
    favorite_movies,
    ios_favorite_movies,
    movies,
    read_only,
    transactional
    )
from models import GetFavoriteResponse, MovieResponseLocalized

logger = logging.getLogger(__name__)

class FavoriteManager(BaseManager):

    @read_only
    async def get_favorites(
        self, 
        user_id: Union[int, str], 
        platform: str = "telegram"
    ) -> Union[List[GetFavoriteResponse], List[MovieResponseLocalized]]:
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
            user_id_value = str(user_id)
        else:
            favorites_table = favorite_movies
            user_field = favorite_movies.c.user_id
            user_id_value = int(user_id) if isinstance(user_id, str) else user_id
        
        favorites_subquery = (
            select(
                favorites_table.c.id,
                favorites_table.c.kp_id,
                favorites_table.c.iswatched
            ).where(user_field == user_id_value) # type: ignore
        ).subquery()

        # Используем таблицу movies для всех платформ
        movies_table = movies
        query = (
            select(
                favorites_subquery.c.id,
                favorites_subquery.c.iswatched,
                movies_table.c.kp_id,
                movies_table.c.title_alt,
                movies_table.c.title_ru,
                movies_table.c.overview,
                movies_table.c.year,
                movies_table.c.google_cloud_url,
                movies_table.c.rating_kp,
                movies_table.c.rating_imdb,
                movies_table.c.movie_length,
                movies_table.c.genres,
                movies_table.c.countries,
                movies_table.c.background_color,
            )
            .select_from(
                movies_table.join(favorites_subquery, favorites_subquery.c.kp_id == movies_table.c.kp_id)
            )
        )

        result = await self.session.execute(query)
        rows = result.fetchall()

        # Возвращаем разные модели в зависимости от платформы
        if platform == "ios":
            return [
                MovieResponseLocalized(
                    movie_id=row.kp_id,
                    imdb_id=None,
                    name=row.title_ru or "",
                    title=row.title_alt or "",
                    overview_ru=row.overview or "",
                    overview_en=None,
                    poster_url_kp=row.google_cloud_url or "",
                    poster_url_tmdb=None,
                    year=row.year,
                    rating_kp=row.rating_kp,
                    rating_imdb=row.rating_imdb,
                    movie_length=row.movie_length,
                    genres_ru=row.genres or [],
                    genres_en=None,
                    countries_ru=row.countries or [],
                    countries_en=None,
                    background_color_kp=row.background_color,
                    background_color_tmdb=None,
                ) for row in rows
            ]
        else:  # telegram
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
    async def add_favorite(self, user_id: Union[int, str], kp_id: int, platform: str = "telegram", is_watched: bool = False) -> None:
        """
        Добавляет фильм в избранное.
        
        Args:
            user_id: ID пользователя (int для Telegram) или device_id (str для iOS)
            kp_id: ID фильма на Кинопоиске
            platform: 'telegram' or 'ios'
            is_watched: Флаг просмотренного фильма (по умолчанию False)
        """
        # Выбираем таблицу в зависимости от платформы
        if platform == "ios":
            favorites_table = ios_favorite_movies
            user_field = ios_favorite_movies.c.device_id
            user_id_value = str(user_id)
            values = {"device_id": user_id_value, "kp_id": kp_id, "iswatched": is_watched}
        else:
            favorites_table = favorite_movies
            user_field = favorite_movies.c.user_id
            user_id_value = int(user_id) if isinstance(user_id, str) else user_id
            values = {"user_id": user_id_value, "kp_id": kp_id, "iswatched": is_watched}
        
        result = await self.session.execute(
            select(favorites_table).where(
                (user_field == user_id_value) & # type: ignore
                (favorites_table.c.kp_id == kp_id) # type: ignore
            )
        )
        exists = result.scalar_one_or_none()
        if not exists:
            await self.session.execute(
                insert(favorites_table).values(**values)
            )
            logger.info(
                f"[FavoriteManager] Фильм добавлен в favorites: user_id={user_id}, "
                f"kp_id={kp_id}, platform={platform}, is_watched={is_watched}"
            )
        else:
            logger.debug(
                f"[FavoriteManager] Фильм уже был в favorites: user_id={user_id}, "
                f"kp_id={kp_id}, platform={platform}"
            )

    @transactional
    async def remove_favorite(self, user_id: Union[int, str], kp_id: int, platform: str = "telegram") -> None:
        """Удаляет фильм из избранного"""
        if platform == "ios":
            favorites_table = ios_favorite_movies
            user_field = ios_favorite_movies.c.device_id
            user_id_value = str(user_id)
        else:
            favorites_table = favorite_movies
            user_field = favorite_movies.c.user_id
            user_id_value = int(user_id) if isinstance(user_id, str) else user_id
        
        await self.session.execute(
            delete(favorites_table).where(
                (user_field == user_id_value) & # type: ignore
                (favorites_table.c.kp_id == kp_id) # type: ignore
            )
        )

    @transactional
    async def mark_watched(self, user_id: Union[int, str], kp_id: int, is_watched: bool, platform: str = "telegram") -> None:
        """Отмечает фильм как просмотренный/непросмотренный"""
        if platform == "ios":
            favorites_table = ios_favorite_movies
            user_field = ios_favorite_movies.c.device_id
            user_id_value = str(user_id)
        else:
            favorites_table = favorite_movies
            user_field = favorite_movies.c.user_id
            user_id_value = int(user_id) if isinstance(user_id, str) else user_id
        
        await self.session.execute(
            update(favorites_table)
            .where(
                (user_field == user_id_value) & # type: ignore
                (favorites_table.c.kp_id == kp_id) # type: ignore
            )
            .values(iswatched=is_watched)
        )
