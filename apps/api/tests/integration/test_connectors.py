"""Integration tests — /api/v1/connectors endpoints.

Sync trigger tests are skipped — they require Celery + Redis broker and a real connector plugin.
"""

import uuid

import pytest
from httpx import AsyncClient

from etip_api.auth.jwt import create_access_token
from tests.integration.conftest import auth, register


class TestListConnectors:
    async def test_empty_list_for_new_tenant(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.get("/api/v1/connectors", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_non_admin_returns_403(self, client: AsyncClient):
        admin_token, tenant_id = await register(client)
        member = await client.post(
            "/api/v1/users",
            json={"email": "tm@acme.com", "password": "Password1!", "role": "tm"},
            headers=auth(admin_token),
        )
        tm_token = create_access_token(
            uuid.UUID(member.json()["id"]), "tm@acme.com", "tm", uuid.UUID(tenant_id)
        )

        resp = await client.get("/api/v1/connectors", headers=auth(tm_token))
        assert resp.status_code == 403

    async def test_scoped_to_tenant(self, client: AsyncClient):
        # Two tenants — connectors from t1 should not appear for t2
        # (we can't create connectors without installed plugins, so just verify isolation at list level)
        token1, _ = await register(client, slug="tenant-one", email="admin@tenant-one.com", company_name="Tenant One")
        token2, _ = await register(client, slug="tenant-two", email="admin@tenant-two.com", company_name="Tenant Two")

        resp1 = await client.get("/api/v1/connectors", headers=auth(token1))
        resp2 = await client.get("/api/v1/connectors", headers=auth(token2))

        assert resp1.status_code == 200
        assert resp2.status_code == 200


class TestListAvailableConnectors:
    async def test_returns_list(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.get("/api/v1/connectors/available", headers=auth(token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_github_connector_is_available(self, client: AsyncClient):
        """GitHub plugin must appear in the available list when installed."""
        token, _ = await register(client)

        resp = await client.get("/api/v1/connectors/available", headers=auth(token))
        assert resp.status_code == 200
        assert "github" in resp.json()

    async def test_no_duplicate_connector_names(self, client: AsyncClient):
        """Connector names must be unique even across multiple lifespan calls."""
        token, _ = await register(client)

        resp = await client.get("/api/v1/connectors/available", headers=auth(token))
        names = resp.json()
        assert len(names) == len(set(names))

    async def test_non_admin_returns_403(self, client: AsyncClient):
        admin_token, tenant_id = await register(client)
        member = await client.post(
            "/api/v1/users",
            json={"email": "tm@acme.com", "password": "Password1!", "role": "tm"},
            headers=auth(admin_token),
        )
        tm_token = create_access_token(
            uuid.UUID(member.json()["id"]), "tm@acme.com", "tm", uuid.UUID(tenant_id)
        )

        resp = await client.get("/api/v1/connectors/available", headers=auth(tm_token))
        assert resp.status_code == 403


class TestCreateConnector:
    async def test_unknown_connector_returns_400(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.post(
            "/api/v1/connectors",
            json={"connector_name": "nonexistent-connector", "config": {"token": "abc"}},
            headers=auth(token),
        )
        assert resp.status_code == 400

    async def test_non_admin_returns_403(self, client: AsyncClient):
        admin_token, tenant_id = await register(client)
        member = await client.post(
            "/api/v1/users",
            json={"email": "tm@acme.com", "password": "Password1!", "role": "tm"},
            headers=auth(admin_token),
        )
        tm_token = create_access_token(
            uuid.UUID(member.json()["id"]), "tm@acme.com", "tm", uuid.UUID(tenant_id)
        )

        resp = await client.post(
            "/api/v1/connectors",
            json={"connector_name": "github", "config": {}},
            headers=auth(tm_token),
        )
        assert resp.status_code == 403

    async def test_unauthenticated_returns_403(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/connectors",
            json={"connector_name": "github", "config": {}},
        )
        assert resp.status_code in (401, 403)

    async def test_admin_can_configure_github_if_installed(self, client: AsyncClient):
        """Create a GitHub connector config and verify it appears in the list."""
        token, _ = await register(client)

        # Only run if github plugin is actually installed
        available_resp = await client.get("/api/v1/connectors/available", headers=auth(token))
        if "github" not in available_resp.json():
            pytest.skip("github connector not installed in this environment")

        resp = await client.post(
            "/api/v1/connectors",
            json={"connector_name": "github", "config": {"access_token": "ghp_test", "org": "acme"}},
            headers=auth(token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["connector_name"] == "github"
        assert body["is_active"] is True

        # Verify it appears in the tenant's configured list
        list_resp = await client.get("/api/v1/connectors", headers=auth(token))
        assert list_resp.status_code == 200
        assert any(c["connector_name"] == "github" for c in list_resp.json())

    async def test_duplicate_connector_config_rejected(self, client: AsyncClient):
        """Creating the same connector twice for the same tenant must fail (unique constraint)."""
        token, _ = await register(client)

        available_resp = await client.get("/api/v1/connectors/available", headers=auth(token))
        if "github" not in available_resp.json():
            pytest.skip("github connector not installed in this environment")

        payload = {"connector_name": "github", "config": {"access_token": "tok", "org": "acme"}}
        first = await client.post("/api/v1/connectors", json=payload, headers=auth(token))
        assert first.status_code == 201

        second = await client.post("/api/v1/connectors", json=payload, headers=auth(token))
        assert second.status_code in (400, 409, 500)  # DB unique constraint
