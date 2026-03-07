"""
E2E tests for movie streaming WebSocket flow (/movie_streaming-ws).

Sends search criteria and validates streamed movie objects
match the MovieResponseLocalized / MatchedMovie contract.

Run:
    pytest backend/tests/e2e/test_movie_stream.py -m e2e -v
"""
import pytest

from .conftest import run_qa_scenario, run_movie_stream


# Required fields that both backend (MovieResponseLocalized) and iOS (MatchedMovie) expect
REQUIRED_MOVIE_FIELDS = {"movie_id", "title", "year"}

# Optional but expected fields in a well-formed response
EXPECTED_MOVIE_FIELDS = {
    "name", "overview_ru", "overview_en",
    "poster_url_kp", "poster_url_tmdb",
    "rating_kp", "rating_imdb",
    "genres_ru", "genres_en",
    "background_color_kp", "background_color_tmdb",
}


def _validate_movie(movie: dict, locale: str = "ru"):
    """Validate a single movie object has correct structure."""
    # Required fields
    for field in REQUIRED_MOVIE_FIELDS:
        assert field in movie, f"Movie missing required field '{field}': {movie.get('movie_id', '?')}"

    assert isinstance(movie["movie_id"], int), "movie_id must be int"
    assert movie["movie_id"] > 0, f"Invalid movie_id: {movie['movie_id']}"
    assert isinstance(movie["year"], int), "year must be int"

    # Poster URL should exist for at least one locale
    has_poster = bool(movie.get("poster_url_kp")) or bool(movie.get("poster_url_tmdb"))
    assert has_poster, f"Movie {movie['movie_id']} has no poster URL"

    # Name or title should be non-empty
    has_name = bool(movie.get("name")) or bool(movie.get("title"))
    assert has_name, f"Movie {movie['movie_id']} has no name/title"

    # Genres should be list of dicts with 'name' key if present
    for genre_field in ("genres_ru", "genres_en"):
        genres = movie.get(genre_field)
        if genres is not None:
            assert isinstance(genres, list), f"{genre_field} must be a list"
            for g in genres:
                assert isinstance(g, dict), f"{genre_field} items must be dicts"
                assert "name" in g, f"{genre_field} items must have 'name' key"


# -- Tests --------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_stream_comedy_movies():
    """Full flow: QA -> search criteria -> stream movies for comedy."""
    # Step 1: Get search criteria from QA agent
    qa_result = await run_qa_scenario(
        query="хочу комедию",
        follow_up_answers=["любой", "любой", "любой"],
    )
    assert qa_result.succeeded, f"QA failed: {qa_result.error}"

    # Step 2: Stream movies with those criteria
    stream_result = await run_movie_stream(
        criteria=qa_result.search_criteria,
        locale="ru",
    )
    assert stream_result.error is None, f"Stream failed: {stream_result.error}"
    assert len(stream_result.movies) > 0, "No movies returned"

    # Step 3: Validate movie structure
    for movie in stream_result.movies:
        _validate_movie(movie, locale="ru")

    # Check no duplicate movie_ids
    ids = [m["movie_id"] for m in stream_result.movies]
    assert len(ids) == len(set(ids)), (
        f"Duplicate movie_ids in stream: {[x for x in ids if ids.count(x) > 1]}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_stream_en_locale():
    """Stream movies with EN locale and validate EN fields."""
    qa_result = await run_qa_scenario(
        query="I want a thriller",
        locale="en",
        follow_up_answers=["any", "any"],
    )
    assert qa_result.succeeded, f"QA failed: {qa_result.error}"

    stream_result = await run_movie_stream(
        criteria=qa_result.search_criteria,
        locale="en",
    )
    assert stream_result.error is None, f"Stream failed: {stream_result.error}"
    assert len(stream_result.movies) > 0

    for movie in stream_result.movies:
        _validate_movie(movie, locale="en")
        # EN locale should have title
        assert movie.get("title"), f"Movie {movie['movie_id']} missing title for EN locale"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_stream_with_direct_criteria():
    """Stream movies with manually constructed criteria (bypass QA)."""
    criteria = {
        "query": "научная фантастика, космос",
        "genres": ["фантастика"],
        "atmospheres": [],
        "start_year": 2000,
        "end_year": 2026,
        "rating_kp": 0.0,
        "rating_imdb": 0.0,
    }

    stream_result = await run_movie_stream(criteria=criteria, locale="ru")
    assert stream_result.error is None, f"Stream failed: {stream_result.error}"
    assert len(stream_result.movies) > 0

    for movie in stream_result.movies:
        _validate_movie(movie)


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_stream_smoke():
    """Quick smoke: stream a few movies with simple criteria."""
    criteria = {
        "query": "интересный фильм",
        "genres": [],
        "atmospheres": [],
        "start_year": 1900,
        "end_year": 2026,
        "rating_kp": 0.0,
        "rating_imdb": 0.0,
    }

    stream_result = await run_movie_stream(criteria=criteria, locale="ru", max_movies=5)
    assert stream_result.error is None, f"Stream failed: {stream_result.error}"
    assert len(stream_result.movies) > 0, "No movies returned"
    _validate_movie(stream_result.movies[0])


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_stream_similar_to_movie():
    """Stream movies similar to a specific movie via movie_name."""
    criteria = {
        "query": "научная фантастика, виртуальная реальность",
        "movie_name": "Матрица",
        "genres": ["фантастика", "боевик"],
        "atmospheres": [],
        "start_year": 1900,
        "end_year": 2026,
        "rating_kp": 0.0,
        "rating_imdb": 0.0,
    }

    stream_result = await run_movie_stream(criteria=criteria, locale="ru")
    assert stream_result.error is None, f"Stream failed: {stream_result.error}"
    assert len(stream_result.movies) > 0

    for movie in stream_result.movies:
        _validate_movie(movie)

    # Movies similar to Matrix should not include Matrix itself
    movie_names = [
        (m.get("name") or "").lower()
        for m in stream_result.movies
    ]
    assert not any("матрица" == n for n in movie_names), (
        "Similar movies should not include the source movie itself"
    )
