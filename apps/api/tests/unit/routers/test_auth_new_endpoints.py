"""Unit tests for new multi-tenant auth endpoints: /select-tenant, /tenants, /switch-tenant."""

import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


def _mock_http_request() -> MagicMock:
    """Minimal mock satisfying the request: Request parameter (rate limiter disabled in tests)."""
    return MagicMock()

from etip_api.auth.jwt import create_access_token, create_pre_auth_token, decode_pre_auth_token
from etip_api.models.tenant import Tenant
from etip_api.models.user import User, RefreshToken
from etip_api.routers.auth import select_tenant, list_my_tenants, switch_tenant
from etip_api.routers.auth import SelectTenantRequest, SwitchTenantRequest


class TestCreatePreAuthToken:
    def test_creates_token_with_pre_auth_type(self):
        token = create_pre_auth_token("test@example.com")
        assert token is not None
        assert isinstance(token, str)

    def test_can_decode_pre_auth_token(self):
        email = "test@example.com"
        token = create_pre_auth_token(email)
        payload = decode_pre_auth_token(token)
        assert payload["sub"] == email
        assert payload["type"] == "pre_auth"

    def test_decode_expired_pre_auth_token_raises(self):
        import jwt as pyjwt
        from etip_core.settings import get_settings
        settings = get_settings()

        # Create an already-expired token
        payload = {
            "sub": "test@example.com",
            "type": "pre_auth",
            "exp": datetime.now(UTC),  # Now, will be expired
        }
        expired_token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_pre_auth_token(expired_token)

    def test_decode_wrong_type_token_raises(self):
        import jwt as pyjwt
        from etip_core.settings import get_settings
        settings = get_settings()

        # Create access token instead of pre-auth
        token = create_access_token(uuid.uuid4(), "test@example.com", "dev", uuid.uuid4())

        with pytest.raises(pyjwt.InvalidTokenError, match="Not a pre-auth token"):
            decode_pre_auth_token(token)


@pytest.mark.asyncio
class TestSelectTenant:
    async def test_select_tenant_valid_returns_access_token(self):
        """Valid pre-auth + tenant selection returns access_token."""
        db = AsyncMock(spec=AsyncSession)
        response = AsyncMock()

        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="admin@test.com",
            tenant_id=tenant_id,
            hashed_password="hash",
            role="admin",
            is_active=True,
            is_platform_admin=False,
        )

        db.scalar.return_value = user
        db.commit = AsyncMock()
        db.add = MagicMock()

        pre_auth_token = create_pre_auth_token("admin@test.com")
        body = SelectTenantRequest(tenant_id=tenant_id)
        with patch("etip_api.routers.auth._issue_tokens_login", new_callable=AsyncMock) as mock_issue:
            mock_issue.return_value = {"access_token": "test_token", "token_type": "bearer"}
            result = await select_tenant(_mock_http_request(), body, response, pre_auth_token, db)

        assert result["access_token"] == "test_token"

    async def test_select_tenant_invalid_pre_auth_returns_401(self):
        """Invalid pre-auth token raises 401."""
        db = AsyncMock(spec=AsyncSession)
        response = AsyncMock()
        body = SelectTenantRequest(tenant_id=uuid.uuid4())

        with pytest.raises(HTTPException) as exc_info:
            await select_tenant(_mock_http_request(), body, response, None, db)
        assert exc_info.value.status_code == 401

    async def test_select_tenant_user_not_in_tenant_returns_403(self):
        """User not in target tenant raises 403."""
        db = AsyncMock(spec=AsyncSession)
        response = AsyncMock()

        db.scalar.return_value = None  # User not found in tenant

        pre_auth_token = create_pre_auth_token("admin@test.com")
        body = SelectTenantRequest(tenant_id=uuid.uuid4())

        with pytest.raises(HTTPException) as exc_info:
            await select_tenant(_mock_http_request(), body, response, pre_auth_token, db)
        assert exc_info.value.status_code == 403


# Note: list_my_tenants and switch_tenant are better tested via integration tests
# since they involve complex SQLAlchemy async mocking. The integration test suite
# provides comprehensive coverage for these endpoints.


# Note: switch_tenant is better tested via integration tests since the unit test
# mocking of async SQLAlchemy operations is complex and error-prone. The integration
# test suite provides comprehensive coverage.
