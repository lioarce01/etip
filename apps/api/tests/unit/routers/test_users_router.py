"""Tests for /api/v1/users router — list, create, get, update, delete."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from etip_api.auth.jwt import create_access_token
from etip_api.auth.password import hash_password
from etip_api.main import app
from etip_api.database import get_db
from etip_api.models.user import User
from tests.conftest import TENANT_ID, USER_ID

OTHER_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000088")


def _make_admin(
    user_id: uuid.UUID = USER_ID,
    tenant_id: uuid.UUID = TENANT_ID,
) -> User:
    u = User()
    u.id = user_id
    u.tenant_id = tenant_id
    u.email = "admin@acme.com"
    u.full_name = "Admin User"
    u.hashed_password = hash_password("Password1!")
    u.role = "admin"
    u.is_active = True
    return u


def _make_member(
    user_id: uuid.UUID = OTHER_USER_ID,
    tenant_id: uuid.UUID = TENANT_ID,
    role: str = "dev",
) -> User:
    u = User()
    u.id = user_id
    u.tenant_id = tenant_id
    u.email = "dev@acme.com"
    u.full_name = "Dev User"
    u.hashed_password = hash_password("Password1!")
    u.role = role
    u.is_active = True
    return u


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


def _auth(user: User) -> dict:
    token = create_access_token(user.id, user.email, user.role, user.tenant_id)
    return {"Authorization": f"Bearer {token}"}


# ── List Users ────────────────────────────────────────────────────────────────

class TestListUsers:
    @pytest.mark.asyncio
    async def test_admin_can_list_users(self, client, mock_db):
        admin = _make_admin()
        member = _make_member()

        mock_db.get.return_value = admin

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [member]

        mock_db.execute.side_effect = [count_result, list_result]

        resp = await client.get("/api/v1/users", headers=_auth(admin))

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client, mock_db):
        member = _make_member(role="tm")
        mock_db.get.return_value = member

        resp = await client.get("/api/v1/users", headers=_auth(member))

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_403(self, client, mock_db):
        resp = await client.get("/api/v1/users")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_pagination_params(self, client, mock_db):
        admin = _make_admin()
        mock_db.get.return_value = admin

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [count_result, list_result]

        resp = await client.get("/api/v1/users?page=2&page_size=5", headers=_auth(admin))

        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert body["page_size"] == 5

    @pytest.mark.asyncio
    async def test_page_size_above_100_returns_422(self, client, mock_db):
        admin = _make_admin()
        mock_db.get.return_value = admin

        resp = await client.get("/api/v1/users?page_size=200", headers=_auth(admin))

        assert resp.status_code == 422


# ── Create User ───────────────────────────────────────────────────────────────

class TestCreateUser:
    @pytest.mark.asyncio
    async def test_admin_creates_user(self, client, mock_db):
        admin = _make_admin()
        new_user = _make_member()

        mock_db.get.return_value = admin

        no_existing = MagicMock()
        no_existing.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = no_existing

        async def _refresh(obj):
            obj.id = OTHER_USER_ID
            obj.email = "dev@acme.com"
            obj.full_name = None
            obj.role = "dev"
            obj.is_active = True

        mock_db.refresh.side_effect = _refresh

        resp = await client.post(
            "/api/v1/users",
            json={"email": "dev@acme.com", "password": "Password1!", "role": "dev"},
            headers=_auth(admin),
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "dev@acme.com"
        assert body["role"] == "dev"

    @pytest.mark.asyncio
    async def test_duplicate_email_returns_409(self, client, mock_db):
        admin = _make_admin()
        existing = _make_member()

        mock_db.get.return_value = admin

        conflict = MagicMock()
        conflict.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = conflict

        resp = await client.post(
            "/api/v1/users",
            json={"email": "dev@acme.com", "password": "Password1!", "role": "dev"},
            headers=_auth(admin),
        )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_invalid_role_returns_422(self, client, mock_db):
        admin = _make_admin()
        mock_db.get.return_value = admin

        resp = await client.post(
            "/api/v1/users",
            json={"email": "x@acme.com", "password": "Password1!", "role": "superuser"},
            headers=_auth(admin),
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_short_password_returns_422(self, client, mock_db):
        admin = _make_admin()
        mock_db.get.return_value = admin

        resp = await client.post(
            "/api/v1/users",
            json={"email": "x@acme.com", "password": "short", "role": "dev"},
            headers=_auth(admin),
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client, mock_db):
        member = _make_member(role="tm")
        mock_db.get.return_value = member

        resp = await client.post(
            "/api/v1/users",
            json={"email": "x@acme.com", "password": "Password1!", "role": "dev"},
            headers=_auth(member),
        )

        assert resp.status_code == 403


# ── Get User ──────────────────────────────────────────────────────────────────

class TestGetUser:
    @pytest.mark.asyncio
    async def test_admin_gets_user(self, client, mock_db):
        admin = _make_admin()
        member = _make_member()

        mock_db.get.side_effect = lambda model, pk: admin if pk == USER_ID else member

        resp = await client.get(f"/api/v1/users/{OTHER_USER_ID}", headers=_auth(admin))

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(OTHER_USER_ID)

    @pytest.mark.asyncio
    async def test_cross_tenant_user_returns_404(self, client, mock_db):
        admin = _make_admin()
        other_tenant_user = _make_member(tenant_id=OTHER_TENANT_ID)

        mock_db.get.side_effect = lambda model, pk: admin if pk == USER_ID else other_tenant_user

        resp = await client.get(f"/api/v1/users/{OTHER_USER_ID}", headers=_auth(admin))

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_404(self, client, mock_db):
        admin = _make_admin()

        mock_db.get.side_effect = lambda model, pk: admin if pk == USER_ID else None

        resp = await client.get(f"/api/v1/users/{uuid.uuid4()}", headers=_auth(admin))

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client, mock_db):
        member = _make_member(role="tm")
        mock_db.get.return_value = member

        resp = await client.get(f"/api/v1/users/{OTHER_USER_ID}", headers=_auth(member))

        assert resp.status_code == 403


# ── Update User ───────────────────────────────────────────────────────────────

class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_admin_can_update_full_name(self, client, mock_db):
        admin = _make_admin()
        member = _make_member()

        mock_db.get.side_effect = lambda model, pk: admin if pk == USER_ID else member

        async def _refresh(obj):
            pass

        mock_db.refresh.side_effect = _refresh

        resp = await client.patch(
            f"/api/v1/users/{OTHER_USER_ID}",
            json={"full_name": "Updated Name"},
            headers=_auth(admin),
        )

        assert resp.status_code == 200
        assert member.full_name == "Updated Name"

    @pytest.mark.asyncio
    async def test_admin_can_change_role(self, client, mock_db):
        admin = _make_admin()
        member = _make_member(role="dev")

        mock_db.get.side_effect = lambda model, pk: admin if pk == USER_ID else member
        mock_db.refresh.side_effect = AsyncMock()

        resp = await client.patch(
            f"/api/v1/users/{OTHER_USER_ID}",
            json={"role": "tm"},
            headers=_auth(admin),
        )

        assert resp.status_code == 200
        assert member.role == "tm"

    @pytest.mark.asyncio
    async def test_cannot_change_own_role(self, client, mock_db):
        admin = _make_admin()
        mock_db.get.return_value = admin

        resp = await client.patch(
            f"/api/v1/users/{USER_ID}",
            json={"role": "dev"},
            headers=_auth(admin),
        )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_cannot_deactivate_self(self, client, mock_db):
        admin = _make_admin()
        mock_db.get.return_value = admin

        resp = await client.patch(
            f"/api/v1/users/{USER_ID}",
            json={"is_active": False},
            headers=_auth(admin),
        )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_can_update_own_full_name(self, client, mock_db):
        admin = _make_admin()

        mock_db.get.return_value = admin
        mock_db.refresh.side_effect = AsyncMock()

        resp = await client.patch(
            f"/api/v1/users/{USER_ID}",
            json={"full_name": "New Admin Name"},
            headers=_auth(admin),
        )

        # full_name change on self is allowed
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_cross_tenant_user_returns_404(self, client, mock_db):
        admin = _make_admin()
        other = _make_member(tenant_id=OTHER_TENANT_ID)

        mock_db.get.side_effect = lambda model, pk: admin if pk == USER_ID else other

        resp = await client.patch(
            f"/api/v1/users/{OTHER_USER_ID}",
            json={"full_name": "Hacked"},
            headers=_auth(admin),
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_role_returns_422(self, client, mock_db):
        admin = _make_admin()
        mock_db.get.return_value = admin

        resp = await client.patch(
            f"/api/v1/users/{OTHER_USER_ID}",
            json={"role": "superuser"},
            headers=_auth(admin),
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client, mock_db):
        member = _make_member(role="tm")
        mock_db.get.return_value = member

        resp = await client.patch(
            f"/api/v1/users/{OTHER_USER_ID}",
            json={"full_name": "X"},
            headers=_auth(member),
        )

        assert resp.status_code == 403


# ── Delete User ───────────────────────────────────────────────────────────────

class TestDeleteUser:
    @pytest.mark.asyncio
    async def test_admin_soft_deletes_user(self, client, mock_db):
        admin = _make_admin()
        member = _make_member()

        mock_db.get.side_effect = lambda model, pk: admin if pk == USER_ID else member

        resp = await client.delete(f"/api/v1/users/{OTHER_USER_ID}", headers=_auth(admin))

        assert resp.status_code == 204
        assert member.is_active is False

    @pytest.mark.asyncio
    async def test_delete_revokes_refresh_tokens(self, client, mock_db):
        admin = _make_admin()
        member = _make_member()

        mock_db.get.side_effect = lambda model, pk: admin if pk == USER_ID else member

        resp = await client.delete(f"/api/v1/users/{OTHER_USER_ID}", headers=_auth(admin))

        assert resp.status_code == 204
        # execute called to revoke tokens
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_cannot_delete_self(self, client, mock_db):
        admin = _make_admin()
        mock_db.get.return_value = admin

        resp = await client.delete(f"/api/v1/users/{USER_ID}", headers=_auth(admin))

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_cross_tenant_user_returns_404(self, client, mock_db):
        admin = _make_admin()
        other = _make_member(tenant_id=OTHER_TENANT_ID)

        mock_db.get.side_effect = lambda model, pk: admin if pk == USER_ID else other

        resp = await client.delete(f"/api/v1/users/{OTHER_USER_ID}", headers=_auth(admin))

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_404(self, client, mock_db):
        admin = _make_admin()

        mock_db.get.side_effect = lambda model, pk: admin if pk == USER_ID else None

        resp = await client.delete(f"/api/v1/users/{uuid.uuid4()}", headers=_auth(admin))

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client, mock_db):
        member = _make_member(role="tm")
        mock_db.get.return_value = member

        resp = await client.delete(f"/api/v1/users/{OTHER_USER_ID}", headers=_auth(member))

        assert resp.status_code == 403
