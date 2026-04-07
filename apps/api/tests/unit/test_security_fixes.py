"""
Tests that verify each security fix from the vibe-audit hardening pass.

1. SQL injection — parameterized bindparams in get_db / auth register
2. Production secret validation — Settings raises on default values
3. Rate limiting — auth endpoints return 429 after limit exceeded
4. Security headers — middleware injects X-Content-Type-Options etc.
5. Exception narrowing — select_tenant catches only jwt errors, not all exceptions
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from etip_api.main import app
from etip_api.limiter import limiter


# ── Helpers ───────────────────────────────────────────────────────────────────

class _FakeRequest:
    """Minimal stand-in for starlette.requests.Request (rate limiter disabled)."""
    class state:
        tenant_id = None


# ── 1. SQL Injection — parameterized queries ─────────────────────────────────

class TestParameterizedRLSQuery:
    """get_db must use .bindparams() — never f-string interpolation."""

    @pytest.mark.asyncio
    async def test_get_db_uses_bindparams_not_fstring(self):
        """The RLS SET statement must carry a bound parameter, not inline SQL."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from starlette.requests import Request as StarletteRequest

        executed_statements = []

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        async def _capture_execute(stmt, *args, **kwargs):
            executed_statements.append(stmt)
            return MagicMock()

        mock_session.execute = _capture_execute

        mock_factory = MagicMock(return_value=mock_session)

        tenant_id = str(uuid.uuid4())

        scope = {
            "type": "http",
            "method": "GET",
            "headers": [],
            "query_string": b"",
            "path": "/",
        }

        fake_request = MagicMock()
        fake_request.state = MagicMock()
        fake_request.state.tenant_id = tenant_id

        with patch("etip_api.database.AsyncSessionLocal", mock_factory):
            from etip_api.database import get_db
            gen = get_db(fake_request)
            await gen.__anext__()
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass

        assert executed_statements, "No SQL statement was executed"
        stmt = executed_statements[0]

        # The statement must use a named bind parameter, not raw interpolation
        compiled = stmt.compile()
        assert ":tid" in str(stmt), (
            f"Expected ':tid' bind parameter in RLS statement, got: {stmt}"
        )
        assert tenant_id not in str(stmt), (
            f"tenant_id must NOT be interpolated directly into the SQL string, got: {stmt}"
        )

    def test_rls_statement_string_has_no_fstring_pattern(self):
        """Regression: verify source does not contain the unsafe f-string pattern."""
        import inspect
        from etip_api import database
        source = inspect.getsource(database)
        assert "f\"SET LOCAL rls.tenant_id = '{" not in source, (
            "Found f-string SQL interpolation in database.py — use .bindparams() instead"
        )

    def test_auth_register_rls_has_no_fstring_pattern(self):
        """Regression: auth.py register must not use f-string in SET LOCAL."""
        import inspect
        from etip_api.routers import auth
        source = inspect.getsource(auth)
        assert "f\"SET LOCAL rls.tenant_id = '{" not in source, (
            "Found f-string SQL interpolation in auth.py — use .bindparams() instead"
        )


# ── 2. Production secret validation ──────────────────────────────────────────

class TestProductionSecretValidation:
    """Settings must raise ValueError when default secrets are used in production."""

    def test_default_jwt_secret_blocked_in_production(self):
        """Booting with APP_ENV=production and default JWT_SECRET must fail."""
        from pydantic import ValidationError
        from etip_core.settings import Settings, _DEFAULT_JWT_SECRET, _DEFAULT_ENCRYPTION_KEY
        from cryptography.fernet import Fernet

        real_key = Fernet.generate_key().decode()

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                app_env="production",
                jwt_secret=_DEFAULT_JWT_SECRET,
                connector_encryption_key=real_key,
            )
        assert "JWT_SECRET" in str(exc_info.value)

    def test_default_encryption_key_blocked_in_production(self):
        """Booting with APP_ENV=production and default CONNECTOR_ENCRYPTION_KEY must fail."""
        import secrets
        from pydantic import ValidationError
        from etip_core.settings import Settings, _DEFAULT_ENCRYPTION_KEY

        real_jwt = secrets.token_hex(32)

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                app_env="production",
                jwt_secret=real_jwt,
                connector_encryption_key=_DEFAULT_ENCRYPTION_KEY,
            )
        assert "CONNECTOR_ENCRYPTION_KEY" in str(exc_info.value)

    def test_defaults_allowed_in_development(self):
        """Default secrets must not block development startup."""
        from etip_core.settings import Settings, _DEFAULT_JWT_SECRET, _DEFAULT_ENCRYPTION_KEY

        # Should not raise
        s = Settings(
            app_env="development",
            jwt_secret=_DEFAULT_JWT_SECRET,
            connector_encryption_key=_DEFAULT_ENCRYPTION_KEY,
        )
        assert s.app_env == "development"

    def test_real_secrets_pass_in_production(self):
        """Valid secrets in production must not raise."""
        import secrets
        from cryptography.fernet import Fernet
        from etip_core.settings import Settings

        s = Settings(
            app_env="production",
            jwt_secret=secrets.token_hex(32),
            connector_encryption_key=Fernet.generate_key().decode(),
        )
        assert s.app_env == "production"


# ── 3. Security headers ───────────────────────────────────────────────────────

class TestSecurityHeaders:
    """Responses must include the security headers injected by SecurityHeadersMiddleware."""

    @pytest.mark.asyncio
    async def test_health_response_has_content_type_options(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    @pytest.mark.asyncio
    async def test_health_response_has_frame_options(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    @pytest.mark.asyncio
    async def test_health_response_has_xss_protection(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.headers.get("x-xss-protection") == "1; mode=block"

    @pytest.mark.asyncio
    async def test_health_response_has_referrer_policy(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_hsts_absent_in_development(self):
        """HSTS header must NOT be injected outside production."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert "strict-transport-security" not in resp.headers


# ── 4. Rate limiting — endpoint registration ─────────────────────────────────

class TestRateLimitingRegistration:
    """Verify that rate-limited endpoints have the limiter decorator applied."""

    def test_login_has_rate_limit_decoration(self):
        """login() must be wrapped by slowapi — check for _rate_limits attribute."""
        from etip_api.routers.auth import login
        assert hasattr(login, "_rate_limits") or hasattr(login, "__wrapped__"), (
            "login endpoint does not appear to be rate-limited by slowapi"
        )

    def test_register_has_rate_limit_decoration(self):
        from etip_api.routers.auth import register
        assert hasattr(register, "_rate_limits") or hasattr(register, "__wrapped__"), (
            "register endpoint does not appear to be rate-limited by slowapi"
        )

    def test_refresh_has_rate_limit_decoration(self):
        from etip_api.routers.auth import refresh
        assert hasattr(refresh, "_rate_limits") or hasattr(refresh, "__wrapped__"), (
            "refresh endpoint does not appear to be rate-limited by slowapi"
        )

    def test_select_tenant_has_rate_limit_decoration(self):
        from etip_api.routers.auth import select_tenant
        assert hasattr(select_tenant, "_rate_limits") or hasattr(select_tenant, "__wrapped__"), (
            "select_tenant endpoint does not appear to be rate-limited by slowapi"
        )

    @pytest.mark.asyncio
    async def test_login_returns_429_after_limit_exceeded(self):
        """POST /auth/login must return 429 once the per-IP limit is exceeded."""
        from etip_api.database import get_db_public

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        # Return empty result so login → 401 (no matching user), not a DB error
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        async def _mock_get_db_public(request=None):
            yield mock_session

        limiter.enabled = True
        app.dependency_overrides[get_db_public] = _mock_get_db_public
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                responses = []
                for _ in range(12):
                    resp = await client.post(
                        "/auth/login",
                        json={"email": "test@test.com", "password": "wrong"},
                    )
                    responses.append(resp.status_code)
            assert 429 in responses, (
                f"Expected a 429 after 10 requests, got status codes: {responses}"
            )
        finally:
            limiter.enabled = False
            app.dependency_overrides.pop(get_db_public, None)


# ── 5. Exception narrowing in select_tenant ──────────────────────────────────

class TestSelectTenantExceptionNarrowing:
    """select_tenant must catch jwt errors specifically, not all exceptions."""

    @pytest.mark.asyncio
    async def test_expired_pre_auth_token_returns_401(self):
        """jwt.ExpiredSignatureError from decode_pre_auth_token → 401."""
        from fastapi import HTTPException
        from etip_api.routers.auth import select_tenant, SelectTenantRequest

        db = AsyncMock(spec=["scalar", "commit", "add"])
        response = AsyncMock()
        body = SelectTenantRequest(tenant_id=uuid.uuid4())

        with patch(
            "etip_api.routers.auth.decode_pre_auth_token",
            side_effect=jwt.ExpiredSignatureError("expired"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await select_tenant(MagicMock(), body, response, "any_token", db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_pre_auth_token_returns_401(self):
        """jwt.InvalidTokenError from decode_pre_auth_token → 401."""
        from fastapi import HTTPException
        from etip_api.routers.auth import select_tenant, SelectTenantRequest

        db = AsyncMock(spec=["scalar", "commit", "add"])
        response = AsyncMock()
        body = SelectTenantRequest(tenant_id=uuid.uuid4())

        with patch(
            "etip_api.routers.auth.decode_pre_auth_token",
            side_effect=jwt.InvalidTokenError("bad token"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await select_tenant(MagicMock(), body, response, "any_token", db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_non_jwt_exception_propagates(self):
        """Non-JWT exceptions must NOT be swallowed by the except clause."""
        from etip_api.routers.auth import select_tenant, SelectTenantRequest

        db = AsyncMock(spec=["scalar", "commit", "add"])
        response = AsyncMock()
        body = SelectTenantRequest(tenant_id=uuid.uuid4())

        with patch(
            "etip_api.routers.auth.decode_pre_auth_token",
            side_effect=RuntimeError("unexpected internal error"),
        ):
            with pytest.raises(RuntimeError):
                await select_tenant(MagicMock(), body, response, "any_token", db)
