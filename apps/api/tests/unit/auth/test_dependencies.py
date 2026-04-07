"""Tests for etip_api.auth.dependencies — get_current_user and require_role."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.testclient import TestClient

from etip_api.auth.dependencies import get_current_user, require_role
from etip_api.auth.jwt import create_access_token
from tests.conftest import TENANT_ID, USER_ID


def _mock_request(tenant_id: str | None = None) -> MagicMock:
    req = MagicMock()
    req.state = MagicMock(spec=[])
    if tenant_id:
        req.state.tenant_id = tenant_id
    return req


@pytest.fixture
def valid_token(make_user) -> str:
    user = make_user(role="tm")
    return create_access_token(user.id, user.email, user.role, user.tenant_id)


@pytest.fixture
def valid_credentials(valid_token) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self, valid_credentials, make_user, mock_db):
        user = make_user(role="tm")
        mock_db.get.return_value = user

        result = await get_current_user(request=_mock_request(), credentials=valid_credentials, db=mock_db)
        assert result.id == USER_ID

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self, mock_db):
        import jwt as pyjwt
        from datetime import timedelta
        from etip_core.settings import get_settings
        settings = get_settings()

        from datetime import UTC, datetime
        payload = {
            "sub": str(USER_ID),
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        }
        expired = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired)

        with pytest.raises(HTTPException) as exc:
            await get_current_user(request=_mock_request(), credentials=creds, db=mock_db)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self, mock_db):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not.a.token")
        with pytest.raises(HTTPException) as exc:
            await get_current_user(request=_mock_request(), credentials=creds, db=mock_db)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_user_raises_401(self, valid_credentials, make_user, mock_db):
        user = make_user(role="tm")
        user.is_active = False
        mock_db.get.return_value = user

        with pytest.raises(HTTPException) as exc:
            await get_current_user(request=_mock_request(), credentials=valid_credentials, db=mock_db)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_user_not_found_raises_401(self, valid_credentials, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            await get_current_user(request=_mock_request(), credentials=valid_credentials, db=mock_db)
        assert exc.value.status_code == 401


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_matching_role_returns_user(self, make_user):
        user = make_user(role="tm")
        checker = require_role("tm", "admin")

        # Inject the user directly as the resolved dependency
        result = await checker(current_user=user)
        assert result.role == "tm"

    @pytest.mark.asyncio
    async def test_wrong_role_raises_403(self, make_user):
        user = make_user(role="dev")
        checker = require_role("tm", "admin")

        with pytest.raises(HTTPException) as exc:
            await checker(current_user=user)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_allowed_when_tm_required(self, make_user):
        user = make_user(role="admin")
        checker = require_role("tm", "admin")
        result = await checker(current_user=user)
        assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_error_message_includes_required_roles(self, make_user):
        user = make_user(role="dev")
        checker = require_role("tm", "admin")

        with pytest.raises(HTTPException) as exc:
            await checker(current_user=user)
        assert "tm" in exc.value.detail or "admin" in exc.value.detail
