import logging

from typing import List, Dict, Union
from fastapi import HTTPException
from sqlalchemy import select, insert

from db_managers.base import (
    BaseManager,
    movies,
    ios_movies,
    skipped_movies,
    ios_skipped_movies,
    favorite_movies,
    ios_favorite_movies,
    read_only,
    transactional
)
from models import MovieResponse, MovieResponseLocalized, MovieDetails, MovieDetailsIOS


logger = logging.getLogger(__name__)


class MovieManager(BaseManager):

    @read_only
    async def get_by_kp_id(self, kp_id: int) -> MovieResponse:
        """
        Получает фильм по kp_id из таблицы movies для Telegram.
        :param kp_id: ID фильма на Кинопоиске
        """
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
            title_alt=row.title_alt or "",
            title_ru=row.title_ru or "",
            overview=row.overview or "",
            poster_url=row.google_cloud_url or "",
            year=row.year,
            rating_kp=float(row.rating_kp) if row.rating_kp is not None else None,
            rating_imdb=float(row.rating_imdb) if row.rating_imdb is not None else None,
            movie_length=row.movie_length,
            genres=row.genres,
            countries=row.countries,
            background_color=row.background_color,
        )

    @read_only
    async def get_ios_movie_by_kp_id(
        self, 
        kp_id: int
    ) -> MovieResponseLocalized:
        """
        Получает фильм по kp_id из таблицы ios_movies для iOS.
        Возвращает объединенную модель с данными для обеих локализаций.
        :param kp_id: ID фильма на Кинопоиске
        """
        query = (
            select(
                ios_movies.c.kp_id,
                ios_movies.c.tmdb_id,
                ios_movies.c.imdb_id,
                ios_movies.c.name,  # русское название
                ios_movies.c.title,  # английское название
                ios_movies.c.description,  # русское описание
                ios_movies.c.overview,  # английское описание
                ios_movies.c.year,
                ios_movies.c.kp_file_path,
                ios_movies.c.tmdb_file_path,
                ios_movies.c.rating_kp,
                ios_movies.c.rating_imdb,
                ios_movies.c.movie_length,
                ios_movies.c.genres,  # русские жанры
                ios_movies.c.genres_tmdb,  # английские жанры
                ios_movies.c.countries,  # русские страны
                ios_movies.c.origin_country,  # английские страны
                ios_movies.c.kp_background_color,
                ios_movies.c.tmdb_background_color,
                ios_movies.c.cast,
                ios_movies.c.directors,
            )
            .where(ios_movies.c.kp_id == kp_id) # type: ignore
        )
        
        result = await self.session.execute(query)
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Фильм не найден")
        
        return MovieResponseLocalized(
            movie_id=row.kp_id,
            imdb_id=row.imdb_id,
            name=row.name or "",
            title=row.title or "",
            overview_ru=row.description,
            overview_en=row.overview,
            poster_url_kp=row.kp_file_path,
            poster_url_tmdb=row.tmdb_file_path,
            year=row.year,
            rating_kp=float(row.rating_kp) if row.rating_kp is not None else None,
            rating_imdb=float(row.rating_imdb) if row.rating_imdb is not None else None,
            movie_length=row.movie_length,
            genres_ru=row.genres,
            genres_en=row.genres_tmdb,
            countries_ru=row.countries,
            countries_en=row.origin_country,
            background_color_kp=row.kp_background_color,
            background_color_tmdb=row.tmdb_background_color,
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
        Асинхронно вставляет новые строки в таблицу movies для Telegram.
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
                logger.info("✅ Фильм %s добавлен в movies", movie_data.title_alt)

    @transactional
    async def insert_ios_movies(self, movies_data: List[MovieDetailsIOS]) -> None:
        """
        Асинхронно вставляет новые строки в таблицу ios_movies для iOS.
        :param movies_data: список объектов MovieDetailsIOS с данными фильмов
        """
        for ios_movie in movies_data:
            query = select(ios_movies.c.kp_id).where(ios_movies.c.kp_id == ios_movie.kp_id) # type: ignore
            result = await self.session.execute(query)
            existing = result.scalar_one_or_none()

            if not existing:
                # Используем все поля из MovieDetailsIOS
                values = {
                    # Основные идентификаторы
                    "kp_id": ios_movie.kp_id,
                    "tmdb_id": ios_movie.tmdb_id,
                    "imdb_id": ios_movie.imdb_id,
                    
                    # Локализованные поля (русский)
                    "name": ios_movie.name,
                    "description": ios_movie.description,
                    "genres": ios_movie.genres,
                    "countries": ios_movie.countries,
                    
                    # Локализованные поля (английский)
                    "title": ios_movie.title,
                    "overview": ios_movie.overview,
                    "genres_tmdb": ios_movie.genres_tmdb,
                    "origin_country": ios_movie.origin_country,
                    
                    # Общие поля
                    "year": ios_movie.year,
                    "movie_length": ios_movie.movie_length,
                    "rating_kp": ios_movie.rating_kp,
                    "rating_imdb": ios_movie.rating_imdb,
                    "popularity_score": ios_movie.popularity_score,
                    
                    # Метаданные
                    "cast": ios_movie.cast,
                    "directors": ios_movie.directors,
                    "keywords": ios_movie.keywords,
                    
                    # Постеры и цвета фона
                    "kp_file_path": ios_movie.kp_file_path,
                    "kp_background_color": ios_movie.kp_background_color,
                    "tmdb_file_path": ios_movie.tmdb_file_path,
                    "tmdb_background_color": ios_movie.tmdb_background_color,
                }
                await self.session.execute(insert(ios_movies).values(**values))
                logger.info("✅ Фильм %s добавлен в ios_movies", ios_movie.title or ios_movie.name)

    @transactional
    async def add_skipped_movies(
        self, 
        user_id: Union[int, str], 
        kp_id: int, 
        platform: str = "telegram"
    ) -> None:
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
    async def check_ios_movie_exists(self, kp_id: int) -> bool:
        """
        Проверяет наличие фильма в ios_movies.
        """
        query = select(ios_movies.c.kp_id).where(ios_movies.c.kp_id == kp_id) # type: ignore
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()
        return existing is not None
    
    @transactional
    async def ensure_ios_movie_from_weaviate(
        self, 
        weaviate_movie_data: dict
    ) -> None:
        """
        Добавляет фильм в ios_movies из данных Weaviate, если его там еще нет.
        Проверка на существование выполняется внутри insert_ios_movies.
        
        Args:
            weaviate_movie_data: словарь с данными фильма из Weaviate (формат из _weaviate_to_movie_dict)
        """
        kp_id = weaviate_movie_data.get("kp_id")
        if not kp_id:
            logger.warning(f"[ensure_ios_movie_from_weaviate] Нет kp_id в данных из Weaviate")
            return
        
        # Преобразуем данные из Weaviate в MovieDetailsIOS
        # Преобразуем жанры и страны из списка строк в список словарей, если нужно
        genres_ru = weaviate_movie_data.get("genres", [])
        genres_ru_dict = [{"name": g} for g in genres_ru] if genres_ru and isinstance(genres_ru[0], str) else (genres_ru or [])
        
        countries_ru = weaviate_movie_data.get("countries", [])
        countries_ru_dict = [{"name": c} for c in countries_ru] if countries_ru and isinstance(countries_ru[0], str) else (countries_ru or [])
        
        genres_tmdb = weaviate_movie_data.get("genres_tmdb", [])
        genres_tmdb_dict = [{"name": g} for g in genres_tmdb] if genres_tmdb and isinstance(genres_tmdb[0], str) else (genres_tmdb or [])
        
        origin_country = weaviate_movie_data.get("origin_country", [])
        origin_country_dict = [{"name": c} for c in origin_country] if origin_country and isinstance(origin_country[0], str) else (origin_country or [])
        
        ios_movie = MovieDetailsIOS(
            kp_id=kp_id,
            tmdb_id=weaviate_movie_data.get("tmdb_id"),
            imdb_id=weaviate_movie_data.get("imdb_id"),
            name=weaviate_movie_data.get("name", ""),
            description=weaviate_movie_data.get("description", ""),
            genres=genres_ru_dict,
            countries=countries_ru_dict,
            title=weaviate_movie_data.get("title"),
            overview=weaviate_movie_data.get("overview"),
            genres_tmdb=genres_tmdb_dict if genres_tmdb_dict else None,
            origin_country=origin_country_dict if origin_country_dict else None,
            year=weaviate_movie_data.get("year", 0),
            movie_length=weaviate_movie_data.get("movieLength"),
            rating_kp=weaviate_movie_data.get("rating_kp"),
            rating_imdb=weaviate_movie_data.get("rating_imdb"),
            popularity_score=weaviate_movie_data.get("popularity_score"),
            cast=weaviate_movie_data.get("cast"),
            directors=weaviate_movie_data.get("directors"),
            keywords=weaviate_movie_data.get("keywords"),
            kp_file_path=weaviate_movie_data.get("kp_file_path"),
            kp_background_color=weaviate_movie_data.get("kp_background_color"),
            tmdb_file_path=weaviate_movie_data.get("tmdb_file_path"),
            tmdb_background_color=weaviate_movie_data.get("tmdb_background_color"),
        )
        
        await self.insert_ios_movies([ios_movie])
        logger.info(f"[ensure_ios_movie_from_weaviate] Фильм kp_id={kp_id} добавлен в ios_movies из Weaviate")

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