"""
E2E test configuration and WebSocket client helpers.

Usage:
    # Run against prod (default):
    pytest backend/tests/e2e/ -m e2e

    # Run against local server:
    TEST_WS_URL=ws://localhost:8000 TEST_HTTP_URL=http://localhost:8000 pytest backend/tests/e2e/ -m e2e
"""
import os
import ssl
import json
import asyncio
import logging
import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import pytest
import websockets

logger = logging.getLogger(__name__)

# -- Config -------------------------------------------------------------------

WS_BASE_URL = os.environ.get("TEST_WS_URL", "wss://auto-gens.com")
HTTP_BASE_URL = os.environ.get("TEST_HTTP_URL", "https://auto-gens.com")
TEST_DEVICE_ID = os.environ.get("TEST_DEVICE_ID", "e2e-test-device-001")

QA_WS_PATH = "/movie-agent-qa"
STREAM_WS_PATH = "/movie_streaming-ws"

# Timeouts (seconds)
WS_RECV_TIMEOUT = 45  # LLM can take up to 30s
SCENARIO_TIMEOUT = 120  # Full scenario with multiple questions
MAX_FOLLOW_UP_QUESTIONS = 5


def _get_ssl_context() -> Optional[ssl.SSLContext]:
    """Build SSL context for wss:// connections. Returns None for ws://."""
    if not WS_BASE_URL.startswith("wss"):
        return None
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        # Fallback: disable verification (OK for testing against own server)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


# -- Data classes -------------------------------------------------------------

@dataclass
class QAResult:
    """Result of running a QA scenario through the agent."""
    messages: list = field(default_factory=list)
    search_criteria: Optional[dict] = None
    questions_asked: list = field(default_factory=list)
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.search_criteria is not None and self.error is None


@dataclass
class StreamResult:
    """Result of running a movie streaming scenario."""
    movies: list = field(default_factory=list)
    completed: bool = False
    error: Optional[str] = None


# -- WebSocket helpers --------------------------------------------------------

async def run_qa_scenario(
    query: str,
    locale: str = "ru",
    follow_up_answers: Optional[list[str]] = None,
    max_questions: int = MAX_FOLLOW_UP_QUESTIONS,
) -> QAResult:
    """
    Connect to QA WebSocket, send query, handle follow-up questions,
    return the final search criteria.

    Args:
        query: Initial user query
        locale: 'ru' or 'en'
        follow_up_answers: Pre-defined answers for follow-up questions.
                          If agent asks more questions than answers provided,
                          uses first suggestion or "any" as fallback.
        max_questions: Safety limit on follow-up questions.
    """
    result = QAResult()
    answers = list(follow_up_answers or [])
    answer_idx = 0
    url = f"{WS_BASE_URL}{QA_WS_PATH}"

    try:
        async with websockets.connect(url, close_timeout=10, ssl=_get_ssl_context()) as ws:
            # Send initial query
            await ws.send(json.dumps({"query": query, "locale": locale}))
            logger.info(f"[E2E QA] Sent query: '{query}' (locale={locale})")

            questions_count = 0
            while questions_count < max_questions:
                raw = await asyncio.wait_for(ws.recv(), timeout=WS_RECV_TIMEOUT)
                msg = json.loads(raw)
                result.messages.append(msg)
                logger.info(f"[E2E QA] Received: type={msg.get('type')}")

                if msg.get("error"):
                    result.error = msg["error"]
                    return result

                msg_type = msg.get("type")

                if msg_type == "search":
                    result.search_criteria = msg
                    logger.info(
                        f"[E2E QA] Search criteria: "
                        f"query='{msg.get('query')}', "
                        f"genres={msg.get('genres')}, "
                        f"atmospheres={msg.get('atmospheres')}, "
                        f"movie_name={msg.get('movie_name')}, "
                        f"cast={msg.get('cast')}, "
                        f"directors={msg.get('directors')}, "
                        f"suggested_titles={msg.get('suggested_titles')}, "
                        f"years={msg.get('start_year')}-{msg.get('end_year')}"
                    )
                    # Wait for the "done" message that follows search
                    try:
                        done_raw = await asyncio.wait_for(ws.recv(), timeout=10)
                        done_msg = json.loads(done_raw)
                        result.messages.append(done_msg)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                        pass
                    return result

                elif msg_type == "done":
                    # Done without search — unusual but possible
                    return result

                elif msg_type == "question":
                    questions_count += 1
                    question_text = msg.get("question", "")
                    suggestions = msg.get("suggestions", [])
                    logger.info(
                        f"[E2E QA] Question #{questions_count}: "
                        f"'{question_text}' | suggestions={suggestions}"
                    )
                    result.questions_asked.append({
                        "question": question_text,
                        "suggestions": suggestions,
                    })

                    # Pick an answer
                    if answer_idx < len(answers):
                        answer = answers[answer_idx]
                        answer_idx += 1
                    elif suggestions:
                        answer = suggestions[0]
                    else:
                        answer = "любой" if locale == "ru" else "any"

                    logger.info(f"[E2E QA] Answering: '{answer}'")
                    await ws.send(json.dumps({"answer": answer, "locale": locale}))

            result.error = f"Too many questions ({questions_count})"

    except asyncio.TimeoutError:
        result.error = "Timeout waiting for server response"
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"

    return result


async def run_movie_stream(
    criteria: dict,
    locale: str = "ru",
    max_movies: int = 30,
    skip_rerank: bool = False,
) -> StreamResult:
    """
    Connect to movie streaming WebSocket, send search criteria,
    collect streamed movies.

    Args:
        criteria: Search criteria dict (from QA result)
        locale: 'ru' or 'en'
        max_movies: Stop after this many movies (safety limit)
    """
    result = StreamResult()
    url = f"{WS_BASE_URL}{STREAM_WS_PATH}"

    payload = {
        "action": "movie_agent_streaming",
        "user_id": TEST_DEVICE_ID,
        "platform": "ios",
        "locale": locale,
        "query": criteria.get("query"),
        "genres": criteria.get("genres", []),
        "atmospheres": criteria.get("atmospheres", []),
        "start_year": criteria.get("start_year", 1900),
        "end_year": criteria.get("end_year", 2026),
        "cast": criteria.get("cast"),
        "directors": criteria.get("directors"),
        "suggested_titles": criteria.get("suggested_titles"),
        "movie_name": criteria.get("movie_name"),
        "rating_kp": criteria.get("rating_kp", 0.0),
        "rating_imdb": criteria.get("rating_imdb", 0.0),
        "skip_rerank": skip_rerank,
    }

    try:
        async with websockets.connect(url, close_timeout=10, ssl=_get_ssl_context()) as ws:
            # Small delay like iOS client does (WebSocket handshake)
            await asyncio.sleep(0.3)
            await ws.send(json.dumps(payload))
            logger.info(f"[E2E Stream] Sent criteria: genres={payload['genres']}, query='{payload['query']}'")

            while len(result.movies) < max_movies:
                raw = await asyncio.wait_for(ws.recv(), timeout=WS_RECV_TIMEOUT)

                # __END__ is sent as plain text
                if raw == "__END__":
                    result.completed = True
                    return result

                if raw == "__ERROR__":
                    result.error = "Server returned __ERROR__"
                    return result

                msg = json.loads(raw)

                if msg.get("error"):
                    result.error = msg["error"]
                    return result

                if msg.get("type") == "movie":
                    result.movies.append(msg)
                    logger.debug(
                        f"[E2E Stream] Movie #{len(result.movies)}: "
                        f"id={msg.get('movie_id')}, name={msg.get('name', msg.get('title', 'N/A'))}"
                    )

    except asyncio.TimeoutError:
        if not result.movies:
            result.error = "Timeout waiting for movies"
    except websockets.exceptions.ConnectionClosed:
        # Server may close connection after sending __END__ or all movies;
        # not an error if we already received movies
        if not result.movies:
            result.error = "Connection closed before receiving any movies"
    except Exception as e:
        if not result.movies:
            result.error = f"{type(e).__name__}: {e}"

    return result


# -- Pytest fixtures ----------------------------------------------------------

@pytest.fixture
def ws_base_url():
    return WS_BASE_URL


@pytest.fixture
def http_base_url():
    return HTTP_BASE_URL


@pytest.fixture
def test_device_id():
    return TEST_DEVICE_ID


# -- Report generation -------------------------------------------------------

REPORTS_DIR = Path(__file__).parent / "reports"


def pytest_sessionfinish(session, exitstatus):
    """Write full-flow results to JSON + Markdown reports."""
    results = getattr(session.config, "_flow_results", [])
    if not results:
        return

    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    suffix = "_no-rerank" if any(r.get("skip_rerank") for r in results) else ""

    # JSON (raw data for diffing between runs)
    json_path = REPORTS_DIR / f"{ts}{suffix}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Markdown (human-readable)
    md_path = REPORTS_DIR / f"{ts}{suffix}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        any_skip = any(r.get("skip_rerank") for r in results)
        mode = "WITHOUT reranker" if any_skip else "WITH reranker"
        f.write(f"# E2E Report — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} ({mode})\n\n")
        for r in results:
            _write_scenario_md(f, r)

    session.config._report_paths = (str(md_path), str(json_path))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print report summary at the end of the test run."""
    results = getattr(config, "_flow_results", [])
    if not results:
        return

    terminalreporter.write_sep("=", "Full Flow Report Summary")
    for r in results:
        movies = r["movies"]
        top = ", ".join(f"{m['name']} ({m['year']})" for m in movies[:3])
        status = f"{len(movies)} movies"
        terminalreporter.write_line(f"  {r['scenario']}: {status} — {top} ...")

    paths = getattr(config, "_report_paths", None)
    if paths:
        terminalreporter.write_line("")
        terminalreporter.write_line(f"  Report:   {paths[0]}")
        terminalreporter.write_line(f"  Raw data: {paths[1]}")


def _write_scenario_md(f, r: dict):
    """Write one scenario section to the markdown report."""
    f.write(f"## {r['scenario']} — \"{r['query']}\"\n\n")

    # Agent behavior
    questions = r.get("questions", [])
    if questions:
        for i, q in enumerate(questions, 1):
            f.write(f"**Q{i}:** {q['question']}  \n")
            f.write(f"Suggestions: {', '.join(q['suggestions'])}\n\n")
    else:
        f.write("*Agent went straight to search — no questions asked*\n\n")

    # Search criteria
    c = r["criteria"]
    parts = [f"genres={c.get('genres', [])}"]
    if c.get("movie_name"):
        parts.append(f"movie_name=\"{c['movie_name']}\"")
    if c.get("cast"):
        parts.append(f"cast={c['cast']}")
    if c.get("directors"):
        parts.append(f"directors={c['directors']}")
    parts.append(f"years={c.get('start_year', '?')}–{c.get('end_year', '?')}")
    if c.get("suggested_titles"):
        parts.append(f"suggested_titles ({len(c['suggested_titles'])})")
    f.write(f"**Search:** {', '.join(parts)}\n\n")

    # Movies table
    movies = r["movies"]
    f.write(f"**Recommended ({len(movies)} movies):**\n\n")
    f.write("| # | Title | Year | KP | IMDB |\n")
    f.write("|---|-------|------|----|------|\n")
    for i, m in enumerate(movies, 1):
        name = m.get("name") or m.get("title") or "?"
        year = m.get("year", "?")
        kp = m.get("rating_kp") or "–"
        imdb = m.get("rating_imdb") or "–"
        f.write(f"| {i} | {name} | {year} | {kp} | {imdb} |\n")
    f.write("\n---\n\n")
