import pytest_asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

from db.user_manager import UserManager


@pytest_asyncio.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)

    session.execute.return_value.scalar_one_or_none.return_value = None

    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    return session

@pytest_asyncio.fixture(scope="function")
def user_manager_mock(mock_session):
    manager = UserManager(session=mock_session)

    manager._check_user_exists = AsyncMock()
    manager._check_referral_exists = AsyncMock()
    manager._save_referral = AsyncMock()

    class FakeTransaction:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            if exc_type is None and getattr(manager, "_should_commit", False):
                await mock_session.commit()

    manager.transaction = MagicMock(return_value=FakeTransaction())

    return manager


@pytest_asyncio.fixture
def test_referrer_user_id():
    return 12345

@pytest_asyncio.fixture
def test_referred_user_id():
    return 23456