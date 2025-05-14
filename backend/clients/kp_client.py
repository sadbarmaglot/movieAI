import json
import aiohttp
import asyncio

from typing import List, Optional

from clients.gc_client import GoogleCloudClient
from models import MovieDetails

class KinopoiskClient:
    BASE_URL = "https://api.kinopoisk.dev/v1.4"
    SEARCH_URL = f"{BASE_URL}/movie/search"

    def __init__(
            self,
            api_key: str,
            gc_client: GoogleCloudClient
    ):
        self.api_key = api_key
        self.headers = {
            "accept": "application/json",
            "X-API-KEY": self.api_key
        }
        self.gc_client = gc_client

    @staticmethod
    def _parse_movie_data(movie_data: dict, title_gpt: Optional[str] = None) -> Optional[MovieDetails]:
        if movie_data.get("type") == "tv-series":
            return None

        poster_url = (movie_data.get("poster") or {}).get("url")

        if not poster_url:
            return None

        year_raw = movie_data.get("year")
        if not year_raw:
            return None

        return MovieDetails.from_kp_data(
            movie_data,
            title_gpt=title_gpt or "",
            poster_url=poster_url,
            year=int(year_raw)
        )

    async def get_by_title(
        self,
        title_gpt: str,
        year: Optional[int] = None,
        genre: Optional[str] = ""
    ) -> Optional[MovieDetails]:
        query = " ".join(filter(None, [title_gpt, str(year) if year else "", genre]))
        url = f"{self.SEARCH_URL}?page=1&limit=1&query={query}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    return None
                try:
                    result = json.loads(await response.text())
                except Exception as e:
                    print(f"Ошибка при парсинге JSON: {e}")
                    return None

        if not result.get("docs"):
            return None

        movie_data = self._parse_movie_data(result["docs"][0], title_gpt=title_gpt)
        if not movie_data:
            return None

        google_cloud_url, background_color = await self.gc_client.download_and_upload_poster(movie_data.poster_url)
        movie_data.google_cloud_url = google_cloud_url
        movie_data.background_color = background_color

        return movie_data

    async def search(self, query: str, limit: int = 20) -> List[MovieDetails]:
        url = f"{self.SEARCH_URL}?page=1&limit={limit}&query={query}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    return []
                try:
                    result = await response.json()
                except Exception as e:
                    print(f"Ошибка при парсинге JSON: {e}")
                    return []
        movies = []
        poster_tasks = []

        for movie_data in result.get("docs", []):
            movie = self._parse_movie_data(movie_data)
            if not movie:
                continue

            poster_tasks.append(self.gc_client.download_and_upload_poster(movie.poster_url))
            movies.append(movie)

        results = await asyncio.gather(*poster_tasks)

        for i, (url, bg) in enumerate(results):
            movies[i].google_cloud_url = url
            movies[i].background_color = bg

        return movies