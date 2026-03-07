"""
E2E test scenario definitions.

Each scenario describes a user query and expected properties of the search result.
Assertions are flexible to account for LLM non-determinism:
  - `expect_genres_any`: at least one of these genres should appear
  - `expect_cast_any`: at least one cast member should appear
  - `expect_movie_name`: movie_name field should match (case-insensitive substring)
  - `expect_year_min` / `expect_year_max`: year range boundaries
  - `expect_no_genres`: genres should be empty (e.g. actor/director queries)
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QAScenario:
    name: str
    query: str
    locale: str = "ru"
    follow_up_answers: list[str] = field(default_factory=list)

    # Flexible assertions on search criteria
    expect_genres_any: Optional[list[str]] = None
    expect_no_genres: bool = False
    expect_cast_any: Optional[list[str]] = None
    expect_directors_any: Optional[list[str]] = None
    expect_movie_name: Optional[str] = None
    expect_year_min: Optional[int] = None
    expect_year_max: Optional[int] = None
    expect_query_contains: Optional[str] = None

    # How many questions is OK before search
    max_questions: int = 3


# -- Russian locale scenarios -------------------------------------------------

SCENARIO_GENRE_COMEDY = QAScenario(
    name="ru_genre_comedy",
    query="хочу комедию",
    expect_genres_any=["комедия"],
    follow_up_answers=["любой", "любой", "любой"],
)

SCENARIO_GENRE_THRILLER = QAScenario(
    name="ru_genre_thriller",
    query="мрачный триллер про маньяка",
    expect_genres_any=["триллер", "детектив", "криминал"],
    follow_up_answers=["любой"],
)

SCENARIO_ACTOR = QAScenario(
    name="ru_actor_keanu",
    query="фильмы с Киану Ривзом",
    expect_cast_any=["Keanu Reeves", "Киану Ривз"],
    expect_no_genres=True,
    follow_up_answers=["любой"],
)

SCENARIO_DIRECTOR = QAScenario(
    name="ru_director_tarantino",
    query="фильмы Тарантино",
    expect_directors_any=["Quentin Tarantino", "Tarantino", "Тарантино"],
    # Agent may reasonably infer genres for well-known directors
    follow_up_answers=["любой"],
)

SCENARIO_SIMILAR = QAScenario(
    name="ru_similar_matrix",
    query="похожее на Матрицу",
    expect_movie_name="Матрица",
    follow_up_answers=["любой"],
)

SCENARIO_DIRECT_SEARCH = QAScenario(
    name="ru_direct_interstellar",
    query="найди Интерстеллар",
    expect_movie_name="Интерстеллар",
    follow_up_answers=["любой"],
)

SCENARIO_YEAR_RANGE = QAScenario(
    name="ru_90s_comedy",
    query="комедии 90-х годов",
    expect_genres_any=["комедия"],
    expect_query_contains="90",
    follow_up_answers=["любой"],
)

# -- English locale scenarios -------------------------------------------------

SCENARIO_EN_THRILLER = QAScenario(
    name="en_genre_thriller",
    query="I want a dark thriller",
    locale="en",
    expect_genres_any=["thriller", "Thriller"],
    follow_up_answers=["any", "any"],
)

SCENARIO_EN_SIMILAR = QAScenario(
    name="en_similar_inception",
    query="movies similar to Inception",
    locale="en",
    expect_movie_name="Inception",
    follow_up_answers=["any"],
)

SCENARIO_EN_ACTOR = QAScenario(
    name="en_actor_dicaprio",
    query="movies with Leonardo DiCaprio",
    locale="en",
    expect_cast_any=["Leonardo DiCaprio"],
    expect_no_genres=True,
    follow_up_answers=["any"],
)


# -- All scenarios for parametrize --------------------------------------------

ALL_QA_SCENARIOS = [
    SCENARIO_GENRE_COMEDY,
    SCENARIO_GENRE_THRILLER,
    SCENARIO_ACTOR,
    SCENARIO_DIRECTOR,
    SCENARIO_SIMILAR,
    SCENARIO_DIRECT_SEARCH,
    SCENARIO_YEAR_RANGE,
    SCENARIO_EN_THRILLER,
    SCENARIO_EN_SIMILAR,
    SCENARIO_EN_ACTOR,
]

# Quick smoke test subset (cheaper to run)
SMOKE_QA_SCENARIOS = [
    SCENARIO_GENRE_COMEDY,
    SCENARIO_SIMILAR,
    SCENARIO_EN_THRILLER,
]
