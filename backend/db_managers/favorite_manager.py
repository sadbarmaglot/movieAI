from typing import List, Union
from sqlalchemy import select, insert, delete, update

from db_managers.base import (
    BaseManager,
    favorite_movies,
    ios_favorite_movies,
    movies,
    ios_movies,
    read_only,
    transactional
    )
from models import GetFavoriteResponse, MovieResponseRU, MovieResponseEN

class FavoriteManager(BaseManager):

    @read_only
    async def get_favorites(
        self, 
        user_id: Union[int, str], 
        platform: str = "telegram",
        locale: str = "ru"
    ) -> Union[List[GetFavoriteResponse], List[MovieResponseRU], List[MovieResponseEN]]:
        """
        Получает избранные фильмы пользователя.
        
        Args:
            user_id: ID пользователя (int для Telegram) или device_id (str для iOS)
            platform: 'telegram' or 'ios'
            locale: 'ru' or 'en' - используется только для iOS
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

        # Выбираем таблицу фильмов в зависимости от платформы
        if platform == "ios":
            movies_table = ios_movies
            if locale == "en":
                # Для английской локализации нужны английские поля
                query = (
                    select(
                        favorites_subquery.c.id,
                        favorites_subquery.c.iswatched,
                        movies_table.c.kp_id,
                        movies_table.c.tmdb_id,
                        movies_table.c.imdb_id,
                        movies_table.c.title,
                        movies_table.c.overview,
                        movies_table.c.year,
                        movies_table.c.tmdb_file_path,
                        movies_table.c.rating_kp,
                        movies_table.c.rating_imdb,
                        movies_table.c.movie_length,
                        movies_table.c.genres_tmdb,
                        movies_table.c.origin_country,
                        movies_table.c.tmdb_background_color,
                    )
                    .select_from(
                        movies_table.join(favorites_subquery, favorites_subquery.c.kp_id == movies_table.c.kp_id)
                    )
                    .where(movies_table.c.tmdb_id.isnot(None))
                )
            else:  # ru
                query = (
                    select(
                        favorites_subquery.c.id,
                        favorites_subquery.c.iswatched,
                        movies_table.c.kp_id,
                        movies_table.c.name,
                        movies_table.c.title,
                        movies_table.c.description,
                        movies_table.c.year,
                        movies_table.c.kp_file_path,
                        movies_table.c.rating_kp,
                        movies_table.c.rating_imdb,
                        movies_table.c.movie_length,
                        movies_table.c.genres,
                        movies_table.c.countries,
                        movies_table.c.kp_background_color,
                    )
                    .select_from(
                        movies_table.join(favorites_subquery, favorites_subquery.c.kp_id == movies_table.c.kp_id)
                    )
                )
        else:
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

        # Возвращаем разные модели в зависимости от платформы и локализации
        if platform == "ios":
            if locale == "en":
                return [
                    MovieResponseEN(
                        movie_id=row.kp_id,
                        imdb_id=row.imdb_id,
                        title=row.title or "",
                        overview=row.overview or "",
                        poster_url=row.tmdb_file_path or "",
                        year=row.year,
                        rating_kp=row.rating_kp,
                        rating_imdb=row.rating_imdb,
                        movie_length=row.movie_length,
                        genres=row.genres_tmdb or [],
                        countries=row.origin_country or [],
                        background_color=row.tmdb_background_color,
                    ) for row in rows
                ]
            else:  # ru
                return [
                    MovieResponseRU(
                        movie_id=row.kp_id,
                        name=row.name or "",
                        title=row.title or "",  # английское название может быть пустым
                        overview=row.description or "",
                        poster_url=row.kp_file_path or "",
                        year=row.year,
                        rating_kp=row.rating_kp,
                        rating_imdb=row.rating_imdb,
                        movie_length=row.movie_length,
                        genres=row.genres or [],
                        countries=row.countries or [],
                        background_color=row.kp_background_color,
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
    async def add_favorite(self, user_id: Union[int, str], kp_id: int, platform: str = "telegram") -> None:
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
            user_id_value = str(user_id)
            values = {"device_id": user_id_value, "kp_id": kp_id}
        else:
            favorites_table = favorite_movies
            user_field = favorite_movies.c.user_id
            user_id_value = int(user_id) if isinstance(user_id, str) else user_id
            values = {"user_id": user_id_value, "kp_id": kp_id}
        
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
