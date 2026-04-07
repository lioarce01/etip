"""
Router test fixtures.

All router tests use FastAPI's dependency_overrides to:
  - Replace get_db with a mock AsyncSession
  - Replace get_current_user / require_role with the desired user
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient

from etip_api.limiter import limiter
from etip_api.main import app
from etip_api.database import get_db
from etip_api.auth.dependencies import get_current_user, require_role


@pytest.fixture(autouse=True)
def disable_rate_limiter():
    """Disable slowapi rate limiting for all unit tests."""
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.execute = AsyncMock()
    db.get = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def override_db(mock_db):
    """Override FastAPI's get_db dependency with a mock session."""
    async def _get_db_override():
        yield mock_db

    app.dependency_overrides[get_db] = _get_db_override
    yield mock_db
    app.dependency_overrides.pop(get_db, None)


def _override_user(user):
    """Helper to override both get_current_user and require_role for any role combo."""
    async def _current_user():
        return user

    def _require_role_factory(*roles):
        async def _check():
            return user
        return _check

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[require_role] = _require_role_factory


@pytest.fixture
def as_tm(make_user, override_db):
    user = make_user(role="tm")
    _override_user(user)
    yield user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_role, None)


@pytest.fixture
def as_admin(make_user, override_db):
    user = make_user(role="admin")
    _override_user(user)
    yield user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_role, None)


@pytest.fixture
def as_dev(make_user, override_db):
    user = make_user(role="dev")
    _override_user(user)
    yield user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_role, None)


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
