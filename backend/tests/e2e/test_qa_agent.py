"""
E2E tests for the QA agent WebSocket flow (/movie-agent-qa).

Simulates an iOS client: sends a query, handles follow-up questions,
validates the final search criteria returned by the agent.

Run:
    pytest backend/tests/e2e/test_qa_agent.py -m e2e -v
    pytest backend/tests/e2e/test_qa_agent.py -m smoke -v   # quick subset
"""
import pytest

from .conftest import run_qa_scenario
from .scenarios import (
    ALL_QA_SCENARIOS,
    SMOKE_QA_SCENARIOS,
    QAScenario,
)


def _assert_scenario(result, scenario: QAScenario):
    """Validate QA result against scenario expectations."""
    assert result.succeeded, (
        f"Scenario '{scenario.name}' failed: {result.error}\n"
        f"Messages: {result.messages}\n"
        f"Questions asked: {result.questions_asked}"
    )

    criteria = result.search_criteria
    assert criteria is not None, f"No search criteria returned for '{scenario.name}'"

    # Genre assertions
    if scenario.expect_genres_any:
        genres = [g.lower() for g in (criteria.get("genres") or [])]
        expected_lower = [g.lower() for g in scenario.expect_genres_any]
        assert any(exp in genres for exp in expected_lower), (
            f"[{scenario.name}] Expected one of {scenario.expect_genres_any} "
            f"in genres, got {criteria.get('genres')}"
        )

    if scenario.expect_no_genres:
        genres = criteria.get("genres") or []
        assert len(genres) == 0, (
            f"[{scenario.name}] Expected empty genres for actor/director query, "
            f"got {genres}"
        )

    # Cast assertions
    if scenario.expect_cast_any:
        cast = criteria.get("cast") or []
        suggested = criteria.get("suggested_titles") or []
        all_names = [n.lower() for n in cast + suggested]
        expected_lower = [n.lower() for n in scenario.expect_cast_any]
        assert any(exp in " ".join(all_names) for exp in expected_lower), (
            f"[{scenario.name}] Expected cast containing one of "
            f"{scenario.expect_cast_any}, got cast={cast}, suggested_titles={suggested}"
        )

    # Director assertions
    if scenario.expect_directors_any:
        directors = criteria.get("directors") or []
        query = criteria.get("query") or ""
        suggested = criteria.get("suggested_titles") or []
        all_text = (" ".join(directors) + " " + query + " " + " ".join(suggested)).lower()
        expected_lower = [n.lower() for n in scenario.expect_directors_any]
        assert any(exp in all_text for exp in expected_lower), (
            f"[{scenario.name}] Expected directors containing one of "
            f"{scenario.expect_directors_any}, got directors={directors}, "
            f"query='{query}', suggested_titles={suggested}"
        )

    # Movie name assertions
    if scenario.expect_movie_name:
        movie_name = criteria.get("movie_name") or ""
        query = criteria.get("query") or ""
        suggested = criteria.get("suggested_titles") or []
        searchable = (movie_name + " " + query + " " + " ".join(suggested)).lower()
        assert scenario.expect_movie_name.lower() in searchable, (
            f"[{scenario.name}] Expected movie_name/query/titles containing "
            f"'{scenario.expect_movie_name}', got movie_name='{movie_name}', "
            f"query='{query}', suggested_titles={suggested}"
        )

    # Year range assertions
    if scenario.expect_year_min is not None:
        start_year = criteria.get("start_year", 1900)
        assert start_year >= scenario.expect_year_min, (
            f"[{scenario.name}] Expected start_year >= {scenario.expect_year_min}, "
            f"got {start_year}"
        )

    if scenario.expect_year_max is not None:
        end_year = criteria.get("end_year", 2026)
        assert end_year <= scenario.expect_year_max, (
            f"[{scenario.name}] Expected end_year <= {scenario.expect_year_max}, "
            f"got {end_year}"
        )

    # Query content assertions
    if scenario.expect_query_contains:
        query = (criteria.get("query") or "").lower()
        assert scenario.expect_query_contains.lower() in query, (
            f"[{scenario.name}] Expected query containing "
            f"'{scenario.expect_query_contains}', got '{query}'"
        )


# -- Parametrized tests -------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.parametrize(
    "scenario",
    ALL_QA_SCENARIOS,
    ids=[s.name for s in ALL_QA_SCENARIOS],
)
@pytest.mark.asyncio
async def test_qa_scenario(scenario: QAScenario):
    """Run a full QA scenario and validate search criteria."""
    result = await run_qa_scenario(
        query=scenario.query,
        locale=scenario.locale,
        follow_up_answers=scenario.follow_up_answers,
        max_questions=scenario.max_questions,
    )
    _assert_scenario(result, scenario)


@pytest.mark.smoke
@pytest.mark.parametrize(
    "scenario",
    SMOKE_QA_SCENARIOS,
    ids=[s.name for s in SMOKE_QA_SCENARIOS],
)
@pytest.mark.asyncio
async def test_qa_smoke(scenario: QAScenario):
    """Quick smoke test with a subset of scenarios."""
    result = await run_qa_scenario(
        query=scenario.query,
        locale=scenario.locale,
        follow_up_answers=scenario.follow_up_answers,
        max_questions=scenario.max_questions,
    )
    _assert_scenario(result, scenario)


# -- Structural tests ---------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_qa_response_structure():
    """Verify that QA responses have correct JSON structure."""
    result = await run_qa_scenario(query="хочу комедию", follow_up_answers=["любой"])
    assert result.succeeded, f"QA failed: {result.error}"

    for msg in result.messages:
        assert isinstance(msg, dict), "Message should be a dict"
        msg_type = msg.get("type")

        if msg_type == "question":
            assert "question" in msg, "Question message must have 'question' field"
            assert "suggestions" in msg, "Question message must have 'suggestions' field"
            assert isinstance(msg["suggestions"], list)

        elif msg_type == "search":
            # Validate all expected fields exist
            for field in ["query", "genres", "atmospheres", "start_year", "end_year"]:
                assert field in msg, f"Search message missing '{field}'"
            assert isinstance(msg["genres"], list)
            assert isinstance(msg["atmospheres"], list)
            assert isinstance(msg["start_year"], int)
            assert isinstance(msg["end_year"], int)

        elif msg_type == "done":
            pass  # Done message is valid

        elif "error" not in msg:
            pytest.fail(f"Unknown message type: {msg_type}, msg={msg}")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_qa_questions_have_suggestions():
    """If agent asks a question, it should provide suggestions."""
    result = await run_qa_scenario(
        query="подбери фильм",
        follow_up_answers=["комедию", "любой", "любой"],
    )
    assert result.succeeded or len(result.questions_asked) > 0, (
        f"Expected at least one question or search: {result.error}"
    )
    for q in result.questions_asked:
        assert isinstance(q["suggestions"], list), "Suggestions must be a list"
