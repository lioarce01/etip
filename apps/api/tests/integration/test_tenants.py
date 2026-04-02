"""Integration tests — /tenants endpoints."""

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth, register


class TestGetMyTenant:
    async def test_returns_tenant_info(self, client: AsyncClient):
        token, tenant_id = await register(client, slug="acme", company_name="ACME Corp")

        resp = await client.get("/tenants/me", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == tenant_id
        assert body["slug"] == "acme"
        assert body["name"] == "ACME Corp"
        assert body["plan"] == "free"

    async def test_unauthenticated_returns_403(self, client: AsyncClient):
        resp = await client.get("/tenants/me")
        assert resp.status_code in (401, 403)

    async def test_dev_role_can_read_tenant(self, client: AsyncClient):
        admin_token, tenant_id = await register(client)

        create = await client.post(
            "/api/v1/users",
            json={"email": "dev@acme.com", "password": "Password1!", "role": "dev"},
            headers=auth(admin_token),
        )
        assert create.status_code == 201

        from etip_api.auth.jwt import create_access_token
        import uuid
        dev_id = uuid.UUID(create.json()["id"])
        dev_token = create_access_token(dev_id, "dev@acme.com", "dev", uuid.UUID(tenant_id))

        resp = await client.get("/tenants/me", headers=auth(dev_token))
        assert resp.status_code == 200


class TestUpdateMyTenant:
    async def test_admin_can_rename_company(self, client: AsyncClient):
        token, _ = await register(client, company_name="Old Name")

        resp = await client.patch(
            "/tenants/me",
            json={"name": "New Name"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    async def test_admin_can_change_slug(self, client: AsyncClient):
        token, _ = await register(client, slug="old-slug")

        resp = await client.patch(
            "/tenants/me",
            json={"slug": "new-slug"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["slug"] == "new-slug"

    async def test_tenant_by_slug_reflects_new_slug(self, client: AsyncClient):
        token, tenant_id = await register(client, slug="original")

        await client.patch("/tenants/me", json={"slug": "updated"}, headers=auth(token))

        resp = await client.get("/auth/tenant-by-slug/updated")
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == tenant_id

    async def test_duplicate_slug_returns_409(self, client: AsyncClient):
        # Register two tenants
        token1, _ = await register(client, slug="company-a", email="a@a.com", company_name="A")
        await register(client, slug="company-b", email="b@b.com", company_name="B")

        resp = await client.patch(
            "/tenants/me",
            json={"slug": "company-b"},
            headers=auth(token1),
        )
        assert resp.status_code == 409

    async def test_invalid_slug_returns_422(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.patch(
            "/tenants/me",
            json={"slug": "INVALID_SLUG"},
            headers=auth(token),
        )
        assert resp.status_code == 422

    async def test_non_admin_returns_403(self, client: AsyncClient):
        admin_token, tenant_id = await register(client)

        create = await client.post(
            "/api/v1/users",
            json={"email": "tm@acme.com", "password": "Password1!", "role": "tm"},
            headers=auth(admin_token),
        )
        import uuid
        from etip_api.auth.jwt import create_access_token
        tm_id = uuid.UUID(create.json()["id"])
        tm_token = create_access_token(tm_id, "tm@acme.com", "tm", uuid.UUID(tenant_id))

        resp = await client.patch("/tenants/me", json={"name": "Hacked"}, headers=auth(tm_token))
        assert resp.status_code == 403
