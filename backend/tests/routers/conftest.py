import pytest
import pytest_asyncio

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from db_managers import UserManager
from main import app

@pytest.fixture
def test_app():
    return app

@pytest_asyncio.fixture(scope="function")
async def async_client(test_app):
    transport = ASGITransport(app=test_app)  # type: ignore
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)

@pytest.fixture
def user_manager_mock(mock_session):
    return UserManager(session=mock_session)


@pytest.fixture
def api_headers():
    return {"X-API-Key": "api_key"}

@pytest.fixture
def test_user_id():
    return 12345

@pytest.fixture
def test_amount():
    return 10

@pytest.fixture
def test_balance():
    return 10

@pytest.fixture
def test_referral_ids():
    return {"user_id": 12345, "referred_by": 999}

@pytest.fixture
def test_log_event_payload(test_user_id):
    return {
        "user_id": test_user_id,
        "session_id": "abc123",
        "page": "matching",
        "action": "like_button",
        "timestamp": "2024-05-13T02:00:00Z",
        "init_data": "tg_init",
        "start_param": "movie_id=42",
        "extra": {"movie_id": 42}
    }