"""Integration tests — /api/v1/users endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from etip_api.auth.jwt import create_access_token
from tests.integration.conftest import auth, register


async def _create_member(client, admin_token, email="dev@acme.com", role="dev"):
    resp = await client.post(
        "/api/v1/users",
        json={"email": email, "password": "Password1!", "role": role},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestListUsers:
    async def test_admin_sees_all_tenant_users(self, client: AsyncClient):
        token, _ = await register(client)
        await _create_member(client, token, "dev1@acme.com")
        await _create_member(client, token, "dev2@acme.com")

        resp = await client.get("/api/v1/users", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        # admin + 2 devs
        assert body["total"] == 3
        assert body["page"] == 1

    async def test_users_scoped_to_tenant(self, client: AsyncClient):
        token1, _ = await register(client, slug="tenant-one", email="admin@tenant-one.com", company_name="Tenant One")
        token2, _ = await register(client, slug="tenant-two", email="admin@tenant-two.com", company_name="Tenant Two")
        await _create_member(client, token1, "dev@t1.com")

        resp = await client.get("/api/v1/users", headers=auth(token2))
        assert resp.status_code == 200
        # tenant2 only has its own admin
        assert resp.json()["total"] == 1

    async def test_non_admin_returns_403(self, client: AsyncClient):
        admin_token, tenant_id = await register(client)
        member = await _create_member(client, admin_token)
        tm_token = create_access_token(
            uuid.UUID(member["id"]), member["email"], member["role"], uuid.UUID(tenant_id)
        )

        resp = await client.get("/api/v1/users", headers=auth(tm_token))
        assert resp.status_code == 403

    async def test_pagination(self, client: AsyncClient):
        token, _ = await register(client)
        for i in range(5):
            await _create_member(client, token, f"dev{i}@acme.com")

        resp = await client.get("/api/v1/users?page=1&page_size=3", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 6
        assert len(body["items"]) == 3
        assert body["page_size"] == 3


class TestCreateUser:
    async def test_creates_user_with_correct_fields(self, client: AsyncClient):
        token, tenant_id = await register(client)

        resp = await client.post(
            "/api/v1/users",
            json={"email": "newdev@acme.com", "password": "Password1!", "role": "dev", "full_name": "New Dev"},
            headers=auth(token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "newdev@acme.com"
        assert body["role"] == "dev"
        assert body["full_name"] == "New Dev"
        assert body["is_active"] is True

    async def test_duplicate_email_returns_409(self, client: AsyncClient):
        token, _ = await register(client)
        await _create_member(client, token, "dup@acme.com")

        resp = await client.post(
            "/api/v1/users",
            json={"email": "dup@acme.com", "password": "Password1!", "role": "dev"},
            headers=auth(token),
        )
        assert resp.status_code == 409

    async def test_same_email_different_tenant_allowed(self, client: AsyncClient):
        token1, _ = await register(client, slug="tenant-one", email="admin@t1.com", company_name="Tenant One")
        token2, _ = await register(client, slug="tenant-two", email="admin@t2.com", company_name="Tenant Two")

        resp1 = await client.post(
            "/api/v1/users",
            json={"email": "shared@example.com", "password": "Password1!", "role": "dev"},
            headers=auth(token1),
        )
        resp2 = await client.post(
            "/api/v1/users",
            json={"email": "shared@example.com", "password": "Password1!", "role": "dev"},
            headers=auth(token2),
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201

    async def test_invalid_role_returns_422(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.post(
            "/api/v1/users",
            json={"email": "x@acme.com", "password": "Password1!", "role": "superuser"},
            headers=auth(token),
        )
        assert resp.status_code == 422

    async def test_short_password_returns_422(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.post(
            "/api/v1/users",
            json={"email": "x@acme.com", "password": "abc", "role": "dev"},
            headers=auth(token),
        )
        assert resp.status_code == 422

    async def test_non_admin_returns_403(self, client: AsyncClient):
        admin_token, tenant_id = await register(client)
        member = await _create_member(client, admin_token)
        member_token = create_access_token(
            uuid.UUID(member["id"]), member["email"], member["role"], uuid.UUID(tenant_id)
        )

        resp = await client.post(
            "/api/v1/users",
            json={"email": "x@acme.com", "password": "Password1!", "role": "dev"},
            headers=auth(member_token),
        )
        assert resp.status_code == 403


class TestGetUser:
    async def test_admin_gets_user_by_id(self, client: AsyncClient):
        token, _ = await register(client)
        member = await _create_member(client, token)

        resp = await client.get(f"/api/v1/users/{member['id']}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == member["id"]

    async def test_nonexistent_user_returns_404(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.get(f"/api/v1/users/{uuid.uuid4()}", headers=auth(token))
        assert resp.status_code == 404

    async def test_cross_tenant_user_returns_404(self, client: AsyncClient):
        token1, _ = await register(client, slug="tenant-one", email="admin@tenant-one.com", company_name="Tenant One")
        token2, _ = await register(client, slug="tenant-two", email="admin@tenant-two.com", company_name="Tenant Two")

        # Get the admin user id from tenant2
        me2 = await client.get("/auth/me", headers=auth(token2))
        t2_user_id = me2.json()["id"]

        # Try to access it from tenant1's admin
        resp = await client.get(f"/api/v1/users/{t2_user_id}", headers=auth(token1))
        assert resp.status_code == 404


class TestUpdateUser:
    async def test_admin_updates_full_name(self, client: AsyncClient):
        token, _ = await register(client)
        member = await _create_member(client, token)

        resp = await client.patch(
            f"/api/v1/users/{member['id']}",
            json={"full_name": "Updated Name"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    async def test_admin_changes_role(self, client: AsyncClient):
        token, _ = await register(client)
        member = await _create_member(client, token, role="dev")

        resp = await client.patch(
            f"/api/v1/users/{member['id']}",
            json={"role": "tm"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "tm"

    async def test_cannot_change_own_role(self, client: AsyncClient):
        token, tenant_id = await register(client)
        me = await client.get("/auth/me", headers=auth(token))
        admin_id = me.json()["id"]

        resp = await client.patch(
            f"/api/v1/users/{admin_id}",
            json={"role": "dev"},
            headers=auth(token),
        )
        assert resp.status_code == 400

    async def test_cannot_deactivate_self(self, client: AsyncClient):
        token, _ = await register(client)
        me = await client.get("/auth/me", headers=auth(token))
        admin_id = me.json()["id"]

        resp = await client.patch(
            f"/api/v1/users/{admin_id}",
            json={"is_active": False},
            headers=auth(token),
        )
        assert resp.status_code == 400

    async def test_can_update_own_full_name(self, client: AsyncClient):
        token, _ = await register(client)
        me = await client.get("/auth/me", headers=auth(token))
        admin_id = me.json()["id"]

        resp = await client.patch(
            f"/api/v1/users/{admin_id}",
            json={"full_name": "New Admin Name"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "New Admin Name"

    async def test_invalid_role_returns_422(self, client: AsyncClient):
        token, _ = await register(client)
        member = await _create_member(client, token)

        resp = await client.patch(
            f"/api/v1/users/{member['id']}",
            json={"role": "god"},
            headers=auth(token),
        )
        assert resp.status_code == 422


class TestDeleteUser:
    async def test_admin_soft_deletes_user(self, client: AsyncClient):
        token, _ = await register(client)
        member = await _create_member(client, token)

        resp = await client.delete(f"/api/v1/users/{member['id']}", headers=auth(token))
        assert resp.status_code == 204

    async def test_deleted_user_cannot_login(self, client: AsyncClient):
        token, tenant_id = await register(client)
        member = await _create_member(client, token, "member@acme.com")

        await client.delete(f"/api/v1/users/{member['id']}", headers=auth(token))

        resp = await client.post(
            "/auth/login",
            json={"email": "member@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        assert resp.status_code == 401

    async def test_cannot_delete_self(self, client: AsyncClient):
        token, _ = await register(client)
        me = await client.get("/auth/me", headers=auth(token))
        admin_id = me.json()["id"]

        resp = await client.delete(f"/api/v1/users/{admin_id}", headers=auth(token))
        assert resp.status_code == 400

    async def test_cross_tenant_user_returns_404(self, client: AsyncClient):
        token1, _ = await register(client, slug="tenant-one", email="admin@tenant-one.com", company_name="Tenant One")
        token2, _ = await register(client, slug="tenant-two", email="admin@tenant-two.com", company_name="Tenant Two")

        me2 = await client.get("/auth/me", headers=auth(token2))
        t2_user_id = me2.json()["id"]

        resp = await client.delete(f"/api/v1/users/{t2_user_id}", headers=auth(token1))
        assert resp.status_code == 404

    async def test_nonexistent_user_returns_404(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.delete(f"/api/v1/users/{uuid.uuid4()}", headers=auth(token))
        assert resp.status_code == 404
