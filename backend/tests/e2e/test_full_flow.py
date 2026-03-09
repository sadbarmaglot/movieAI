"""
E2E full flow: QA agent -> movie streaming -> report.

Runs each scenario through the complete pipeline and collects
recommended movies for tracking and comparison across runs.

Run:
    pytest backend/tests/e2e/test_full_flow.py -m e2e -v --log-cli-level=INFO
    Reports saved to: backend/tests/e2e/reports/

Compare with/without reranker:
    pytest backend/tests/e2e/test_full_flow.py -m e2e -v --skip-rerank
"""
import pytest

from .conftest import run_qa_scenario, run_movie_stream
from .scenarios import ALL_QA_SCENARIOS, QAScenario



@pytest.mark.e2e
@pytest.mark.parametrize(
    "scenario",
    ALL_QA_SCENARIOS,
    ids=[s.name for s in ALL_QA_SCENARIOS],
)
@pytest.mark.asyncio
async def test_full_flow(scenario: QAScenario, request):
    """Run QA -> Stream and record results for reporting."""
    skip_rerank = request.config.getoption("--skip-rerank", default=False)

    # Step 1: QA agent
    qa_result = await run_qa_scenario(
        query=scenario.query,
        locale=scenario.locale,
        follow_up_answers=scenario.follow_up_answers,
        max_questions=scenario.max_questions,
    )
    assert qa_result.succeeded, f"QA failed: {qa_result.error}"

    # Step 2: Stream movies
    stream_result = await run_movie_stream(
        criteria=qa_result.search_criteria,
        locale=scenario.locale,
        skip_rerank=skip_rerank,
    )
    assert stream_result.error is None, f"Stream failed: {stream_result.error}"
    assert len(stream_result.movies) > 0, "No movies returned"

    # Step 3: Record for report
    if not hasattr(request.config, "_flow_results"):
        request.config._flow_results = []

    request.config._flow_results.append({
        "scenario": scenario.name,
        "query": scenario.query,
        "locale": scenario.locale,
        "skip_rerank": skip_rerank,
        "questions": qa_result.questions_asked,
        "criteria": qa_result.search_criteria,
        "movies": [
            {
                "movie_id": m["movie_id"],
                "name": m.get("name") or m.get("title", "?"),
                "title": m.get("title", ""),
                "year": m.get("year"),
                "rating_kp": m.get("rating_kp"),
                "rating_imdb": m.get("rating_imdb"),
            }
            for m in stream_result.movies
        ],
    })
