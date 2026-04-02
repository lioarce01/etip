"""Integration tests — /api/v1/projects endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from etip_api.auth.jwt import create_access_token
from tests.integration.conftest import auth, register

_SKILLS = [{"skill_label": "Python", "level": "senior", "weight": 1.0}]


class TestListProjects:
    async def test_empty_list(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.get("/api/v1/projects", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_returns_created_projects(self, client: AsyncClient):
        token, _ = await register(client)
        await client.post("/api/v1/projects", json={"name": "Project A"}, headers=auth(token))
        await client.post("/api/v1/projects", json={"name": "Project B"}, headers=auth(token))

        resp = await client.get("/api/v1/projects", headers=auth(token))
        assert resp.json()["total"] == 2

    async def test_scoped_to_tenant(self, client: AsyncClient):
        token1, _ = await register(client, slug="tenant-one", email="admin@tenant-one.com", company_name="Tenant One")
        token2, _ = await register(client, slug="tenant-two", email="admin@tenant-two.com", company_name="Tenant Two")

        await client.post("/api/v1/projects", json={"name": "T1 Project"}, headers=auth(token1))

        resp = await client.get("/api/v1/projects", headers=auth(token2))
        assert resp.json()["total"] == 0

    async def test_filter_by_status(self, client: AsyncClient):
        token, _ = await register(client)
        create = await client.post("/api/v1/projects", json={"name": "P1"}, headers=auth(token))
        project_id = create.json()["id"]
        await client.patch(f"/api/v1/projects/{project_id}", json={"status": "active"}, headers=auth(token))
        await client.post("/api/v1/projects", json={"name": "P2"}, headers=auth(token))

        resp = await client.get("/api/v1/projects?status=active", headers=auth(token))
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "P1"

    async def test_dev_role_returns_403(self, client: AsyncClient):
        admin_token, tenant_id = await register(client)
        member = await client.post(
            "/api/v1/users",
            json={"email": "dev@acme.com", "password": "Password1!", "role": "dev"},
            headers=auth(admin_token),
        )
        dev_token = create_access_token(
            uuid.UUID(member.json()["id"]), "dev@acme.com", "dev", uuid.UUID(tenant_id)
        )

        resp = await client.get("/api/v1/projects", headers=auth(dev_token))
        assert resp.status_code == 403


class TestCreateProject:
    async def test_creates_project(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.post(
            "/api/v1/projects",
            json={
                "name": "Backend Rewrite",
                "description": "Migrate to microservices",
                "required_skills": _SKILLS,
            },
            headers=auth(token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Backend Rewrite"
        assert body["status"] == "planning"
        assert len(body["required_skills"]) == 1

    async def test_created_by_is_set(self, client: AsyncClient):
        token, _ = await register(client)
        me = await client.get("/auth/me", headers=auth(token))
        admin_id = me.json()["id"]

        resp = await client.post("/api/v1/projects", json={"name": "P"}, headers=auth(token))
        assert resp.json()["created_by"] == admin_id

    async def test_end_date_before_start_date_returns_422(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.post(
            "/api/v1/projects",
            json={"name": "Bad Dates", "start_date": "2026-06-01", "end_date": "2026-05-01"},
            headers=auth(token),
        )
        assert resp.status_code == 422

    async def test_unauthenticated_returns_403(self, client: AsyncClient):
        resp = await client.post("/api/v1/projects", json={"name": "P"})
        assert resp.status_code in (401, 403)


class TestGetProject:
    async def test_returns_project_by_id(self, client: AsyncClient):
        token, _ = await register(client)
        create = await client.post("/api/v1/projects", json={"name": "My Project"}, headers=auth(token))
        project_id = create.json()["id"]

        resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "My Project"

    async def test_nonexistent_returns_404(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=auth(token))
        assert resp.status_code == 404

    async def test_cross_tenant_returns_404(self, client: AsyncClient):
        token1, _ = await register(client, slug="tenant-one", email="admin@tenant-one.com", company_name="Tenant One")
        token2, _ = await register(client, slug="tenant-two", email="admin@tenant-two.com", company_name="Tenant Two")

        create = await client.post("/api/v1/projects", json={"name": "T2 Project"}, headers=auth(token2))
        project_id = create.json()["id"]

        resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth(token1))
        assert resp.status_code == 404


class TestUpdateProject:
    async def test_updates_name_and_status(self, client: AsyncClient):
        token, _ = await register(client)
        create = await client.post("/api/v1/projects", json={"name": "Old Name"}, headers=auth(token))
        project_id = create.json()["id"]

        resp = await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "New Name", "status": "active"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "New Name"
        assert body["status"] == "active"

    async def test_updates_required_skills(self, client: AsyncClient):
        token, _ = await register(client)
        create = await client.post("/api/v1/projects", json={"name": "P"}, headers=auth(token))
        project_id = create.json()["id"]

        new_skills = [{"skill_label": "Go", "level": "mid", "weight": 0.9}]
        resp = await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"required_skills": new_skills},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["required_skills"][0]["skill_label"] == "Go"

    async def test_cross_tenant_returns_404(self, client: AsyncClient):
        token1, _ = await register(client, slug="tenant-one", email="admin@tenant-one.com", company_name="Tenant One")
        token2, _ = await register(client, slug="tenant-two", email="admin@tenant-two.com", company_name="Tenant Two")

        create = await client.post("/api/v1/projects", json={"name": "T2 P"}, headers=auth(token2))
        project_id = create.json()["id"]

        resp = await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Hacked"},
            headers=auth(token1),
        )
        assert resp.status_code == 404


class TestDeleteProject:
    async def test_admin_deletes_project(self, client: AsyncClient):
        token, _ = await register(client)
        create = await client.post("/api/v1/projects", json={"name": "To Delete"}, headers=auth(token))
        project_id = create.json()["id"]

        resp = await client.delete(f"/api/v1/projects/{project_id}", headers=auth(token))
        assert resp.status_code == 204

    async def test_deleted_project_returns_404(self, client: AsyncClient):
        token, _ = await register(client)
        create = await client.post("/api/v1/projects", json={"name": "Bye"}, headers=auth(token))
        project_id = create.json()["id"]

        await client.delete(f"/api/v1/projects/{project_id}", headers=auth(token))
        resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth(token))
        assert resp.status_code == 404

    async def test_tm_cannot_delete_returns_403(self, client: AsyncClient):
        admin_token, tenant_id = await register(client)
        create = await client.post("/api/v1/projects", json={"name": "P"}, headers=auth(admin_token))
        project_id = create.json()["id"]

        member = await client.post(
            "/api/v1/users",
            json={"email": "tm@acme.com", "password": "Password1!", "role": "tm"},
            headers=auth(admin_token),
        )
        tm_token = create_access_token(
            uuid.UUID(member.json()["id"]), "tm@acme.com", "tm", uuid.UUID(tenant_id)
        )

        resp = await client.delete(f"/api/v1/projects/{project_id}", headers=auth(tm_token))
        assert resp.status_code == 403

    async def test_cross_tenant_returns_404(self, client: AsyncClient):
        token1, _ = await register(client, slug="tenant-one", email="admin@tenant-one.com", company_name="Tenant One")
        token2, _ = await register(client, slug="tenant-two", email="admin@tenant-two.com", company_name="Tenant Two")

        create = await client.post("/api/v1/projects", json={"name": "T2 P"}, headers=auth(token2))
        project_id = create.json()["id"]

        resp = await client.delete(f"/api/v1/projects/{project_id}", headers=auth(token1))
        assert resp.status_code == 404
