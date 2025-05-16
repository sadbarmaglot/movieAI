from typing import List
from sqlalchemy import select, insert, delete, update

from db_managers.base import BaseManager, favorite_movies, movies
from models import GetFavoriteResponse

class FavoriteManager(BaseManager):

    async def get_favorites(self, user_id: int) -> List[GetFavoriteResponse]:
        favorites_subquery = (
            select(
                favorite_movies.c.id,
                favorite_movies.c.kp_id,
                favorite_movies.c.iswatched
            ).where(favorite_movies.c.user_id == user_id) # type: ignore
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

    async def add_favorite(self, user_id: int, kp_id: int) -> None:
        async with self.transaction():
            result = await self.session.execute(
                select(favorite_movies).where(
                    (favorite_movies.c.user_id == user_id) & # type: ignore
                    (favorite_movies.c.kp_id == kp_id) # type: ignore
                )
            )
            exists = result.scalar_one_or_none()
            if not exists:
                await self.session.execute(
                    insert(favorite_movies).values(user_id=user_id, kp_id=kp_id)
                )

    async def remove_favorite(self, user_id: int, kp_id: int) -> None:
        async with self.transaction():
            await self.session.execute(
                delete(favorite_movies).where(
                    (favorite_movies.c.user_id == user_id) & # type: ignore
                    (favorite_movies.c.kp_id == kp_id) # type: ignore
                )
            )

    async def mark_watched(self, user_id: int, kp_id: int, is_watched: bool) -> None:
        async with self.transaction():
            await self.session.execute(
                update(favorite_movies)
                .where(
                    (favorite_movies.c.user_id == user_id) & # type: ignore
                    (favorite_movies.c.kp_id == kp_id) # type: ignore
                )
                .values(iswatched=is_watched)
            )
