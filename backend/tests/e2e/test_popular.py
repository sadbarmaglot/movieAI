"""
E2E tests for REST endpoints.

Tests /get-popular-movies and validates the response matches
MovieResponseLocalized contract expected by iOS MatchedMovie model.

Run:
    pytest backend/tests/e2e/test_popular.py -m e2e -v
"""
import pytest
import httpx

from .conftest import HTTP_BASE_URL, TEST_DEVICE_ID


REQUIRED_FIELDS = {"movie_id", "title", "year"}

LOCALIZED_FIELDS_RU = {"name", "overview_ru", "poster_url_kp", "genres_ru"}
LOCALIZED_FIELDS_EN = {"title", "overview_en", "poster_url_tmdb", "genres_en"}


def _validate_popular_movie(movie: dict):
    """Validate a movie from /get-popular-movies."""
    for field in REQUIRED_FIELDS:
        assert field in movie, f"Missing required field '{field}'"

    assert isinstance(movie["movie_id"], int)
    assert movie["movie_id"] > 0
    assert isinstance(movie["year"], int)
    assert movie["year"] > 1900

    # Should have at least one poster
    has_poster = bool(movie.get("poster_url_kp")) or bool(movie.get("poster_url_tmdb"))
    assert has_poster, f"Movie {movie['movie_id']} has no poster URL"

    # Rating should be reasonable if present
    for rating_field in ("rating_kp", "rating_imdb"):
        rating = movie.get(rating_field)
        if rating is not None:
            assert 0 <= rating <= 10, f"Invalid {rating_field}={rating}"

    # Genres format: list of {"name": "..."} dicts
    for genre_field in ("genres_ru", "genres_en"):
        genres = movie.get(genre_field)
        if genres is not None:
            assert isinstance(genres, list)
            for g in genres:
                assert isinstance(g, dict)
                assert "name" in g


# -- Tests --------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_popular_movies_default():
    """GET /get-popular-movies with default params."""
    async with httpx.AsyncClient(base_url=HTTP_BASE_URL, timeout=30) as client:
        resp = await client.get("/get-popular-movies")

    assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text[:200]}"

    movies = resp.json()
    assert isinstance(movies, list)
    assert len(movies) > 0, "No popular movies returned"

    for movie in movies[:10]:  # Validate first 10
        _validate_popular_movie(movie)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_popular_movies_with_filters():
    """GET /get-popular-movies with year and rating filters."""
    async with httpx.AsyncClient(base_url=HTTP_BASE_URL, timeout=30) as client:
        resp = await client.get("/get-popular-movies", params={
            "limit": 20,
            "min_year": 2020,
            "min_rating_kp": 7.5,
            "locale": "ru",
        })

    assert resp.status_code == 200
    movies = resp.json()
    assert isinstance(movies, list)
    assert len(movies) > 0

    for movie in movies:
        _validate_popular_movie(movie)
        assert movie["year"] >= 2020, f"Movie {movie['movie_id']} year {movie['year']} < 2020"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_popular_movies_en_locale():
    """GET /get-popular-movies with EN locale."""
    async with httpx.AsyncClient(base_url=HTTP_BASE_URL, timeout=30) as client:
        resp = await client.get("/get-popular-movies", params={
            "limit": 10,
            "locale": "en",
        })

    assert resp.status_code == 200
    movies = resp.json()
    assert len(movies) > 0

    for movie in movies:
        _validate_popular_movie(movie)
        assert movie.get("title"), f"Movie {movie['movie_id']} missing title for EN"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_popular_movies_with_user_exclusion():
    """GET /get-popular-movies with user_id to test exclusion logic."""
    async with httpx.AsyncClient(base_url=HTTP_BASE_URL, timeout=30) as client:
        resp = await client.get("/get-popular-movies", params={
            "limit": 10,
            "user_id": TEST_DEVICE_ID,
            "platform": "ios",
        })

    assert resp.status_code == 200
    movies = resp.json()
    assert isinstance(movies, list)
    # May return fewer movies if user has exclusions, but should still work
    if movies:
        _validate_popular_movie(movies[0])


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_popular_smoke():
    """Quick smoke: popular movies endpoint responds."""
    async with httpx.AsyncClient(base_url=HTTP_BASE_URL, timeout=15) as client:
        resp = await client.get("/get-popular-movies", params={"limit": 3})

    assert resp.status_code == 200
    movies = resp.json()
    assert len(movies) > 0
    assert "movie_id" in movies[0]
    assert "title" in movies[0]
