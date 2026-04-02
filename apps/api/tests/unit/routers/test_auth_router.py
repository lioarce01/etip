"""Tests for /auth router — login, refresh, logout, me, change-password."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from etip_api.auth.password import hash_password
from etip_api.main import app
from etip_api.database import get_db
from etip_api.models.user import RefreshToken, User
from tests.conftest import TENANT_ID, USER_ID


def _make_db_user(role: str = "tm", password: str = "Password1!") -> User:
    user = User()
    user.id = USER_ID
    user.tenant_id = TENANT_ID
    user.email = "manager@acme.com"
    user.full_name = "Test Manager"
    user.hashed_password = hash_password(password)
    user.role = role
    user.is_active = True
    return user


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.get = AsyncMock()
    return db


@pytest.fixture
async def client(mock_db) -> AsyncClient:
    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


class TestLogin:
    @pytest.mark.asyncio
    async def test_valid_credentials_returns_access_token(self, client, mock_db):
        user = _make_db_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        resp = await client.post("/auth/login", json={"email": "manager@acme.com", "password": "Password1!", "tenant_id": str(TENANT_ID)})

        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_sets_refresh_cookie(self, client, mock_db):
        user = _make_db_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        resp = await client.post("/auth/login", json={"email": "manager@acme.com", "password": "Password1!", "tenant_id": str(TENANT_ID)})

        assert "refresh_token" in resp.cookies

    @pytest.mark.asyncio
    async def test_wrong_password_returns_401(self, client, mock_db):
        user = _make_db_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        resp = await client.post("/auth/login", json={"email": "manager@acme.com", "password": "WrongPass!", "tenant_id": str(TENANT_ID)})

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_user_returns_401(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = await client.post("/auth/login", json={"email": "nobody@acme.com", "password": "pass", "tenant_id": str(TENANT_ID)})

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_user_returns_401(self, client, mock_db):
        user = _make_db_user()
        user.is_active = False
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        resp = await client.post("/auth/login", json={"email": "manager@acme.com", "password": "Password1!", "tenant_id": str(TENANT_ID)})

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_tenant_returns_401(self, client, mock_db):
        """User exists but the tenant_id in the request doesn't match — must return 401."""
        # DB returns None because the (email, tenant_id) pair doesn't exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        wrong_tenant = uuid.uuid4()
        resp = await client.post(
            "/auth/login",
            json={"email": "manager@acme.com", "password": "Password1!", "tenant_id": str(wrong_tenant)},
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_request_requires_tenant_id(self, client, mock_db):
        """Login payload without tenant_id must be rejected at schema validation."""
        resp = await client.post(
            "/auth/login",
            json={"email": "manager@acme.com", "password": "Password1!"},
        )
        assert resp.status_code == 422


class TestRefresh:
    def _make_db_token(self, raw_token: str, revoked: bool = False) -> RefreshToken:
        t = RefreshToken()
        t.id = uuid.uuid4()
        t.user_id = USER_ID
        t.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        t.expires_at = datetime.now(UTC) + timedelta(days=7)
        t.revoked = revoked
        return t

    @pytest.mark.asyncio
    async def test_valid_refresh_token_returns_new_access_token(self, client, mock_db):
        raw = "valid-refresh-token"
        db_token = self._make_db_token(raw)
        user = _make_db_user()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = db_token
        mock_db.execute.return_value = mock_result
        mock_db.get.return_value = user

        client.cookies.set("refresh_token", raw)
        resp = await client.post("/auth/refresh")
        client.cookies.clear()

        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_no_cookie_returns_401(self, client, mock_db):
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_revoked_token_returns_401(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # revoked → not found
        mock_db.execute.return_value = mock_result

        client.cookies.set("refresh_token", "revoked")
        resp = await client.post("/auth/refresh")
        client.cookies.clear()
        assert resp.status_code == 401


class TestRegister:
    def _make_tenant(self) -> "Tenant":
        from etip_api.models.tenant import Tenant
        t = Tenant()
        t.id = TENANT_ID
        t.slug = "acme-corp"
        t.name = "ACME Corp"
        t.plan = "free"
        return t

    @pytest.mark.asyncio
    async def test_register_creates_tenant_and_returns_token(self, client, mock_db):
        tenant = self._make_tenant()
        user = _make_db_user(role="admin")

        # slug uniqueness check returns None (not taken)
        slug_result = MagicMock()
        slug_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = slug_result

        async def _refresh_side_effect(obj):
            if hasattr(obj, "slug"):
                obj.id = TENANT_ID
            else:
                obj.id = USER_ID
                obj.email = "admin@acme.com"
                obj.role = "admin"
                obj.tenant_id = TENANT_ID

        mock_db.refresh.side_effect = _refresh_side_effect

        # After flush, give the tenant an id so _issue_tokens can use it
        async def _flush_side_effect():
            tenant.id = TENANT_ID
            user.id = USER_ID
            user.tenant_id = TENANT_ID

        mock_db.flush.side_effect = _flush_side_effect

        resp = await client.post(
            "/auth/register",
            json={
                "company_name": "ACME Corp",
                "slug": "acme-corp",
                "email": "admin@acme.com",
                "password": "Password1!",
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_sets_refresh_cookie(self, client, mock_db):
        from etip_api.models.tenant import Tenant

        slug_result = MagicMock()
        slug_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = slug_result

        tenant_obj = Tenant()
        tenant_obj.id = TENANT_ID

        async def _flush_side_effect():
            pass

        mock_db.flush.side_effect = _flush_side_effect

        resp = await client.post(
            "/auth/register",
            json={
                "company_name": "ACME Corp",
                "slug": "acme-corp",
                "email": "admin@acme.com",
                "password": "Password1!",
            },
        )

        assert resp.status_code == 201
        assert "refresh_token" in resp.cookies

    @pytest.mark.asyncio
    async def test_duplicate_slug_returns_409(self, client, mock_db):
        from etip_api.models.tenant import Tenant

        existing = Tenant()
        existing.id = uuid.uuid4()
        existing.slug = "acme-corp"
        slug_result = MagicMock()
        slug_result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = slug_result

        resp = await client.post(
            "/auth/register",
            json={
                "company_name": "Another Corp",
                "slug": "acme-corp",
                "email": "other@other.com",
                "password": "Password1!",
            },
        )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_invalid_slug_returns_422(self, client, mock_db):
        resp = await client.post(
            "/auth/register",
            json={
                "company_name": "Bad Corp",
                "slug": "UPPER-CASE",
                "email": "admin@bad.com",
                "password": "Password1!",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_short_password_returns_422(self, client, mock_db):
        resp = await client.post(
            "/auth/register",
            json={
                "company_name": "ACME Corp",
                "slug": "acme-corp",
                "email": "admin@acme.com",
                "password": "short",
            },
        )
        assert resp.status_code == 422


class TestTenantBySlug:
    @pytest.mark.asyncio
    async def test_valid_slug_returns_tenant_id(self, client, mock_db):
        from etip_api.models.tenant import Tenant

        tenant = Tenant()
        tenant.id = TENANT_ID
        tenant.slug = "acme-corp"
        tenant.name = "ACME Corp"
        tenant.plan = "free"

        result = MagicMock()
        result.scalar_one_or_none.return_value = tenant
        mock_db.execute.return_value = result

        resp = await client.get("/auth/tenant-by-slug/acme-corp")

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == str(TENANT_ID)
        assert body["slug"] == "acme-corp"
        assert body["name"] == "ACME Corp"

    @pytest.mark.asyncio
    async def test_unknown_slug_returns_404(self, client, mock_db):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        resp = await client.get("/auth/tenant-by-slug/no-such-company")

        assert resp.status_code == 404


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_revokes_refresh_token(self, client, mock_db):
        user = _make_db_user()
        from etip_api.auth.jwt import create_access_token
        token = create_access_token(user.id, user.email, user.role, user.tenant_id)
        mock_db.get.return_value = user

        client.cookies.set("refresh_token", "some-token")
        resp = await client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        client.cookies.clear()

        assert resp.status_code == 204
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self, client, mock_db):
        user = _make_db_user()
        from etip_api.auth.jwt import create_access_token
        token = create_access_token(user.id, user.email, user.role, user.tenant_id)
        mock_db.get.return_value = user

        client.cookies.set("refresh_token", "some-token")
        resp = await client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        client.cookies.clear()

        assert resp.status_code == 204
        # Cookie should be deleted (Set-Cookie header with empty value or max-age=0)
        assert "refresh_token" not in resp.cookies or resp.cookies["refresh_token"] == ""

    @pytest.mark.asyncio
    async def test_logout_without_token_returns_403(self, client, mock_db):
        resp = await client.post("/auth/logout")
        assert resp.status_code in (401, 403)


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_valid_change_succeeds(self, client, mock_db):
        user = _make_db_user(password="OldPass1!")
        from etip_api.auth.jwt import create_access_token
        token = create_access_token(user.id, user.email, user.role, user.tenant_id)
        mock_db.get.return_value = user

        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_response_body_is_empty(self, client, mock_db):
        """
        204 No Content must have an empty body.
        Any client calling .json() on this response will get a parse error —
        this test documents the contract so callers know not to parse the body.
        """
        user = _make_db_user(password="OldPass1!")
        from etip_api.auth.jwt import create_access_token
        token = create_access_token(user.id, user.email, user.role, user.tenant_id)
        mock_db.get.return_value = user

        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 204
        assert resp.content == b""

    @pytest.mark.asyncio
    async def test_wrong_current_password_returns_400(self, client, mock_db):
        user = _make_db_user(password="OldPass1!")
        from etip_api.auth.jwt import create_access_token
        token = create_access_token(user.id, user.email, user.role, user.tenant_id)
        mock_db.get.return_value = user

        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "WrongPass!", "new_password": "NewPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Current password is incorrect"

    @pytest.mark.asyncio
    async def test_hashed_password_is_updated_in_session(self, client, mock_db):
        """
        The ORM object held by the session must have its hashed_password field
        mutated so SQLAlchemy flushes the UPDATE on commit.  This guards against
        a regression where the field is set on a detached / different object.
        """
        user = _make_db_user(password="OldPass1!")
        from etip_api.auth.jwt import create_access_token
        from etip_api.auth.password import verify_password
        token = create_access_token(user.id, user.email, user.role, user.tenant_id)
        mock_db.get.return_value = user

        await client.post(
            "/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # The in-memory user object must now verify against the NEW password
        assert verify_password("NewPass1!", user.hashed_password)
        assert not verify_password("OldPass1!", user.hashed_password)

    @pytest.mark.asyncio
    async def test_change_password_revokes_all_sessions(self, client, mock_db):
        user = _make_db_user(password="OldPass1!")
        from etip_api.auth.jwt import create_access_token
        token = create_access_token(user.id, user.email, user.role, user.tenant_id)
        mock_db.get.return_value = user

        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 204
        # execute should have been called to revoke refresh tokens
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_403(self, client, mock_db):
        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
        )
        assert resp.status_code in (401, 403)


class TestMe:
    @pytest.mark.asyncio
    async def test_returns_current_user_profile(self, client, mock_db):
        user = _make_db_user()
        from etip_api.auth.jwt import create_access_token
        token = create_access_token(user.id, user.email, user.role, user.tenant_id)
        mock_db.get.return_value = user

        resp = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "manager@acme.com"
        assert body["role"] == "tm"

    @pytest.mark.asyncio
    async def test_no_token_returns_403(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code in (401, 403)
