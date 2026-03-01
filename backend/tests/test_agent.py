"""Tests for agent functionality: tools, prompts, conversions, tool call parsing."""
import os
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Mock env vars before importing settings
_MOCK_ENV = {
    "BOT_TOKEN": "test",
    "BOT_FEEDBACK_TOKEN": "test",
    "WEB_APP_URL": "http://test",
    "API_KEY": "test",
    "KINOPOISK_API_KEY": "test",
    "SQL_HOST": "localhost",
    "SQL_PORT": "5432",
    "SQL_DB": "test",
    "SQL_USER": "test",
    "SQL_PSWRD": "test",
    "INDEX_PATH": "/tmp",
    "OPENAI_API_KEY": "sk-test",
}
for k, v in _MOCK_ENV.items():
    os.environ.setdefault(k, v)

from models.movies import to_name_dicts
from settings import (
    get_agent_tools,
    CURRENT_YEAR,
    LAST_YEAR,
    SYSTEM_PROMPT_AGENT_RU,
    SYSTEM_PROMPT_AGENT_EN,
)


# ── to_name_dicts ──────────────────────────────────────────────────────

class TestToNameDicts:
    def test_empty_list(self):
        assert to_name_dicts([]) == []

    def test_strings(self):
        assert to_name_dicts(["комедия", "драма"]) == [
            {"name": "комедия"},
            {"name": "драма"},
        ]

    def test_dicts_passthrough(self):
        inp = [{"name": "Comedy"}, {"name": "Drama"}]
        assert to_name_dicts(inp) == inp

    def test_single_string(self):
        assert to_name_dicts(["боевик"]) == [{"name": "боевик"}]

    def test_single_dict(self):
        assert to_name_dicts([{"name": "Action"}]) == [{"name": "Action"}]


# ── get_agent_tools ────────────────────────────────────────────────────

class TestGetAgentTools:
    def test_returns_three_tools_ru(self):
        tools = get_agent_tools("ru")
        assert len(tools) == 3

    def test_returns_three_tools_en(self):
        tools = get_agent_tools("en")
        assert len(tools) == 3

    def test_tool_names(self):
        tools = get_agent_tools("ru")
        names = [t["function"]["name"] for t in tools]
        assert names == ["ask_user_question", "suggest_movie_titles", "search_movies_by_vector"]

    def test_all_descriptions_populated_ru(self):
        for tool in get_agent_tools("ru"):
            fn = tool["function"]
            assert fn.get("description"), f"{fn['name']} missing description"
            for param, schema in fn["parameters"]["properties"].items():
                assert schema.get("description"), f"{fn['name']}.{param} missing description"

    def test_all_descriptions_populated_en(self):
        for tool in get_agent_tools("en"):
            fn = tool["function"]
            assert fn.get("description"), f"{fn['name']} missing description"
            for param, schema in fn["parameters"]["properties"].items():
                assert schema.get("description"), f"{fn['name']}.{param} missing description"

    def test_ru_descriptions_in_russian(self):
        tools = get_agent_tools("ru")
        search_desc = tools[2]["function"]["description"]
        assert "фильм" in search_desc.lower()

    def test_en_descriptions_in_english(self):
        tools = get_agent_tools("en")
        search_desc = tools[2]["function"]["description"]
        assert "movie" in search_desc.lower()

    def test_end_year_dynamic(self):
        tools = get_agent_tools("ru")
        search_props = tools[2]["function"]["parameters"]["properties"]
        assert search_props["end_year"]["default"] == CURRENT_YEAR

    def test_start_year_default(self):
        tools = get_agent_tools("ru")
        search_props = tools[2]["function"]["parameters"]["properties"]
        assert search_props["start_year"]["default"] == 1900

    def test_search_defaults_preserved(self):
        tools = get_agent_tools("ru")
        props = tools[2]["function"]["parameters"]["properties"]
        assert props["genres"]["default"] == []
        assert props["atmospheres"]["default"] == []

    def test_required_fields(self):
        tools = get_agent_tools("ru")
        # ask_user_question requires question
        assert tools[0]["function"]["parameters"]["required"] == ["question"]
        # suggest_movie_titles requires titles + query
        assert set(tools[1]["function"]["parameters"]["required"]) == {"titles", "query"}
        # search_movies_by_vector has no required
        assert tools[2]["function"]["parameters"]["required"] == []

    def test_deepcopy_isolation(self):
        tools_a = get_agent_tools("ru")
        tools_b = get_agent_tools("ru")
        # mutate A
        tools_a[0]["function"]["description"] = "MUTATED"
        # B should be unaffected
        assert tools_b[0]["function"]["description"] != "MUTATED"

    def test_genres_description_no_infer(self):
        """Genres description should warn against inferring genres for actor/director requests."""
        for locale in ("ru", "en"):
            tools = get_agent_tools(locale)
            for tool in tools[1:]:  # suggest + search
                genres_desc = tool["function"]["parameters"]["properties"]["genres"]["description"]
                # Should contain anti-inference rule
                assert "режиссёр" in genres_desc.lower() or "director" in genres_desc.lower(), \
                    f"genres desc ({locale}) missing anti-inference rule"


# ── System Prompts ─────────────────────────────────────────────────────

class TestSystemPrompts:
    def test_ru_contains_current_year(self):
        assert str(CURRENT_YEAR) in SYSTEM_PROMPT_AGENT_RU

    def test_ru_contains_last_year(self):
        assert str(LAST_YEAR) in SYSTEM_PROMPT_AGENT_RU

    def test_en_contains_current_year(self):
        assert str(CURRENT_YEAR) in SYSTEM_PROMPT_AGENT_EN

    def test_ru_movie_name_rule(self):
        assert "movie_name" in SYSTEM_PROMPT_AGENT_RU

    def test_ru_directors_rule(self):
        assert "directors" in SYSTEM_PROMPT_AGENT_RU
        assert "cast" in SYSTEM_PROMPT_AGENT_RU

    def test_ru_series_rule(self):
        assert "сериал" in SYSTEM_PROMPT_AGENT_RU.lower() or "ТОЛЬКО фильмы" in SYSTEM_PROMPT_AGENT_RU

    def test_en_series_rule(self):
        assert "ONLY movies" in SYSTEM_PROMPT_AGENT_EN

    def test_ru_language_rule(self):
        assert "ТОМ ЖЕ языке" in SYSTEM_PROMPT_AGENT_RU

    def test_en_language_rule(self):
        assert "SAME language" in SYSTEM_PROMPT_AGENT_EN

    def test_ru_genre_list_present(self):
        assert "комедия" in SYSTEM_PROMPT_AGENT_RU
        assert "драма" in SYSTEM_PROMPT_AGENT_RU

    def test_en_genre_list_present(self):
        assert "Comedy" in SYSTEM_PROMPT_AGENT_EN
        assert "Drama" in SYSTEM_PROMPT_AGENT_EN

    def test_ru_no_infer_genres_for_actors(self):
        """Prompt should say not to infer genres for actor/director requests."""
        assert "актёр" in SYSTEM_PROMPT_AGENT_RU.lower() or "режиссёр" in SYSTEM_PROMPT_AGENT_RU.lower()

    def test_en_no_infer_genres_for_actors(self):
        assert "actor" in SYSTEM_PROMPT_AGENT_EN.lower() or "director" in SYSTEM_PROMPT_AGENT_EN.lower()


# ── Agent tool call parsing (mock-based) ───────────────────────────────

class TestAgentToolCallParsing:
    """Test that MovieAgent correctly parses tool calls from OpenAI responses."""

    @pytest.fixture
    def mock_agent(self):
        from clients.movie_agent import MovieAgent

        agent = MovieAgent(
            openai_client=AsyncMock(),
            kp_client=MagicMock(),
            recommender=MagicMock(),
        )
        return agent

    def _make_tool_call(self, name: str, arguments: dict):
        """Create a mock tool call object."""
        tc = MagicMock()
        tc.function.name = name
        tc.function.arguments = json.dumps(arguments)
        tc.id = "call_test123"
        return tc

    def _make_response(self, tool_calls=None, content=None):
        """Create a mock OpenAI response."""
        resp = MagicMock()
        choice = MagicMock()
        choice.message.tool_calls = tool_calls
        choice.message.content = content
        choice.finish_reason = "tool_calls" if tool_calls else "stop"
        resp.choices = [choice]
        return resp

    @pytest.mark.asyncio
    async def test_ask_user_question_yields_question(self, mock_agent):
        tool_call = self._make_tool_call("ask_user_question", {
            "question": "Какой жанр?",
            "suggestions": ["Боевик", "Комедия"],
        })
        resp = self._make_response(tool_calls=[tool_call])
        mock_agent.openai_client.chat.completions.create = AsyncMock(return_value=resp)

        results = []
        async for r in mock_agent.run_qa("привет", locale="ru"):
            results.append(r)

        assert len(results) == 1
        assert results[0]["type"] == "question"
        assert results[0]["question"] == "Какой жанр?"
        assert results[0]["suggestions"] == ["Боевик", "Комедия"]

    @pytest.mark.asyncio
    async def test_search_movies_yields_search(self, mock_agent):
        tool_call = self._make_tool_call("search_movies_by_vector", {
            "query": "мрачный триллер",
            "genres": ["триллер"],
            "atmospheres": ["мрачный и атмосферный"],
            "cast": [],
            "directors": [],
            "start_year": 1900,
            "end_year": 2026,
            "rating_kp": 0.0,
            "rating_imdb": 0.0,
        })
        resp = self._make_response(tool_calls=[tool_call])
        mock_agent.openai_client.chat.completions.create = AsyncMock(return_value=resp)

        results = []
        async for r in mock_agent.run_qa("хочу триллер", locale="ru"):
            results.append(r)

        assert len(results) == 1
        assert results[0]["type"] == "search"
        assert results[0]["query"] == "мрачный триллер"
        assert results[0]["genres"] == ["триллер"]

    @pytest.mark.asyncio
    async def test_suggest_titles_yields_search_with_titles(self, mock_agent):
        tool_call = self._make_tool_call("suggest_movie_titles", {
            "titles": ["Матрица", "Джон Уик"],
            "query": "фильмы с Киану Ривзом",
            "genres": [],
            "atmospheres": [],
            "cast": ["Keanu Reeves"],
            "directors": [],
            "rating_kp": 0,
            "rating_imdb": 0,
        })
        resp = self._make_response(tool_calls=[tool_call])
        mock_agent.openai_client.chat.completions.create = AsyncMock(return_value=resp)

        results = []
        async for r in mock_agent.run_qa("фильмы с Киану Ривзом", locale="ru"):
            results.append(r)

        assert len(results) == 1
        assert results[0]["type"] == "search"
        assert results[0]["suggested_titles"] == ["Матрица", "Джон Уик"]
        assert results[0]["cast"] == ["Keanu Reeves"]
        # Genres should be empty for actor request
        assert results[0]["genres"] == []
