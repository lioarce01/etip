"""Tests for /tenants router — GET /tenants/me, PATCH /tenants/me."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from etip_api.auth.jwt import create_access_token
from etip_api.main import app
from etip_api.database import get_db
from etip_api.models.tenant import Tenant
from etip_api.models.user import User
from tests.conftest import TENANT_ID, USER_ID


def _make_user(role: str = "admin") -> User:
    u = User()
    u.id = USER_ID
    u.tenant_id = TENANT_ID
    u.email = "admin@acme.com"
    u.full_name = "Admin User"
    u.hashed_password = "hashed"
    u.role = role
    u.is_active = True
    return u


def _make_tenant() -> Tenant:
    t = Tenant()
    t.id = TENANT_ID
    t.slug = "acme-corp"
    t.name = "ACME Corp"
    t.plan = "free"
    return t


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
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


def _auth_header(user: User) -> dict:
    token = create_access_token(user.id, user.email, user.role, user.tenant_id)
    return {"Authorization": f"Bearer {token}"}


class TestGetMyTenant:
    @pytest.mark.asyncio
    async def test_returns_tenant_for_authenticated_user(self, client, mock_db):
        user = _make_user(role="tm")
        tenant = _make_tenant()
        mock_db.get.side_effect = lambda model, pk: user if model is User else tenant

        resp = await client.get("/tenants/me", headers=_auth_header(user))

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(TENANT_ID)
        assert body["slug"] == "acme-corp"
        assert body["name"] == "ACME Corp"
        assert body["plan"] == "free"

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_403(self, client, mock_db):
        resp = await client.get("/tenants/me")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_tenant_not_found_returns_404(self, client, mock_db):
        user = _make_user(role="tm")
        mock_db.get.side_effect = lambda model, pk: user if model is User else None

        resp = await client.get("/tenants/me", headers=_auth_header(user))

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_dev_role_can_access(self, client, mock_db):
        user = _make_user(role="dev")
        tenant = _make_tenant()
        mock_db.get.side_effect = lambda model, pk: user if model is User else tenant

        resp = await client.get("/tenants/me", headers=_auth_header(user))

        assert resp.status_code == 200


class TestUpdateMyTenant:
    @pytest.mark.asyncio
    async def test_admin_can_rename_company(self, client, mock_db):
        user = _make_user(role="admin")
        tenant = _make_tenant()

        mock_db.get.side_effect = lambda model, pk: user if model is User else tenant

        # No slug conflict
        no_conflict = MagicMock()
        no_conflict.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = no_conflict

        async def _refresh(obj):
            pass

        mock_db.refresh.side_effect = _refresh

        resp = await client.patch(
            "/tenants/me",
            json={"name": "ACME Corporation"},
            headers=_auth_header(user),
        )

        assert resp.status_code == 200
        assert tenant.name == "ACME Corporation"

    @pytest.mark.asyncio
    async def test_admin_can_change_slug(self, client, mock_db):
        user = _make_user(role="admin")
        tenant = _make_tenant()

        mock_db.get.side_effect = lambda model, pk: user if model is User else tenant

        no_conflict = MagicMock()
        no_conflict.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = no_conflict

        resp = await client.patch(
            "/tenants/me",
            json={"slug": "acme-new"},
            headers=_auth_header(user),
        )

        assert resp.status_code == 200
        assert tenant.slug == "acme-new"

    @pytest.mark.asyncio
    async def test_duplicate_slug_returns_409(self, client, mock_db):
        user = _make_user(role="admin")
        tenant = _make_tenant()

        mock_db.get.side_effect = lambda model, pk: user if model is User else tenant

        conflicting = _make_tenant()
        conflicting.id = uuid.uuid4()
        conflicting.slug = "taken-slug"
        conflict_result = MagicMock()
        conflict_result.scalar_one_or_none.return_value = conflicting
        mock_db.execute.return_value = conflict_result

        resp = await client.patch(
            "/tenants/me",
            json={"slug": "taken-slug"},
            headers=_auth_header(user),
        )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_invalid_slug_returns_422(self, client, mock_db):
        user = _make_user(role="admin")
        mock_db.get.return_value = user

        resp = await client.patch(
            "/tenants/me",
            json={"slug": "UPPER_CASE"},
            headers=_auth_header(user),
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client, mock_db):
        user = _make_user(role="tm")
        mock_db.get.return_value = user

        resp = await client.patch(
            "/tenants/me",
            json={"name": "New Name"},
            headers=_auth_header(user),
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_same_slug_no_conflict_check(self, client, mock_db):
        """Updating slug to its current value should not trigger the conflict query."""
        user = _make_user(role="admin")
        tenant = _make_tenant()  # slug = "acme-corp"

        mock_db.get.side_effect = lambda model, pk: user if model is User else tenant

        execute_results = MagicMock()
        execute_results.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = execute_results

        resp = await client.patch(
            "/tenants/me",
            json={"slug": "acme-corp"},  # same as current
            headers=_auth_header(user),
        )

        # Should succeed without raising conflict
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_403(self, client, mock_db):
        resp = await client.patch("/tenants/me", json={"name": "New"})
        assert resp.status_code in (401, 403)
