"""Tests for /api/v1/projects router."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import PROJECT_ID, TENANT_ID, USER_ID


class TestListProjects:
    @pytest.mark.asyncio
    async def test_tm_can_list_projects(self, client, as_tm, override_db):
        mock_count = MagicMock()
        mock_count.scalar_one.return_value = 0
        mock_items = MagicMock()
        mock_items.scalars.return_value.all.return_value = []
        override_db.execute.side_effect = [mock_count, mock_items]

        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body

    @pytest.mark.asyncio
    async def test_pagination_defaults(self, client, as_tm, override_db):
        mock_count = MagicMock()
        mock_count.scalar_one.return_value = 0
        mock_items = MagicMock()
        mock_items.scalars.return_value.all.return_value = []
        override_db.execute.side_effect = [mock_count, mock_items]

        resp = await client.get("/api/v1/projects")
        body = resp.json()
        assert body["page"] == 1
        assert body["page_size"] == 20

    @pytest.mark.asyncio
    async def test_list_query_scoped_to_tenant(self, client, as_tm, override_db):
        """The SELECT must include tenant_id in the WHERE clause."""
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        captured = {}
        mock_count = MagicMock()
        mock_count.scalar_one.return_value = 0
        mock_items = MagicMock()
        mock_items.scalars.return_value.all.return_value = []
        call_count = 0

        async def _capture(stmt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            captured[call_count] = stmt
            return mock_count if call_count == 1 else mock_items

        override_db.execute = _capture

        await client.get("/api/v1/projects")

        compiled = captured[1].compile(dialect=pg_dialect())
        assert "tenant_id" in str(compiled)


class TestProjectDateValidation:
    @pytest.mark.asyncio
    async def test_end_before_start_returns_422(self, client, as_tm, override_db):
        resp = await client.post(
            "/api/v1/projects",
            json={
                "name": "Bad Dates",
                "start_date": "2026-06-01",
                "end_date": "2026-04-01",   # before start
                "required_skills": [],
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_same_start_end_date_is_valid(self, client, as_tm, override_db, make_project):
        async def mock_refresh(obj):
            obj.id = PROJECT_ID
            obj.status = "planning"
            obj.required_skills = []

        override_db.refresh = mock_refresh

        resp = await client.post(
            "/api/v1/projects",
            json={
                "name": "One-day Project",
                "start_date": "2026-06-01",
                "end_date": "2026-06-01",   # same day — valid
                "required_skills": [],
            },
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_patch_end_before_start_returns_422(self, client, as_tm, override_db, make_project):
        project = make_project()
        override_db.get.return_value = project

        resp = await client.patch(
            f"/api/v1/projects/{PROJECT_ID}",
            json={"start_date": "2026-09-01", "end_date": "2026-08-01"},
        )
        assert resp.status_code == 422


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_tm_can_create_project(self, client, as_tm, override_db, make_project):
        project = make_project()
        override_db.refresh.side_effect = lambda obj: None

        # Simulate db.add + commit (project gets an id)
        async def mock_refresh(obj):
            obj.id = PROJECT_ID
            obj.status = "planning"
            obj.required_skills = obj.required_skills or []

        override_db.refresh = mock_refresh

        resp = await client.post(
            "/api/v1/projects",
            json={
                "name": "Backend Rewrite",
                "description": "Go microservices",
                "required_skills": [
                    {"skill_label": "Go", "level": "senior", "weight": 1.0}
                ],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Backend Rewrite"

    @pytest.mark.asyncio
    async def test_missing_name_returns_422(self, client, as_tm, override_db):
        resp = await client.post("/api/v1/projects", json={"description": "No name"})
        assert resp.status_code == 422


class TestGetProject:
    @pytest.mark.asyncio
    async def test_returns_project_for_valid_id(self, client, as_tm, override_db, make_project):
        project = make_project()
        override_db.get.return_value = project

        resp = await client.get(f"/api/v1/projects/{PROJECT_ID}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Backend Rewrite"

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_project(self, client, as_tm, override_db):
        override_db.get.return_value = None

        resp = await client.get(f"/api/v1/projects/{PROJECT_ID}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_project_returns_404(self, client, as_tm, override_db, make_project):
        """A project belonging to a different tenant must be invisible."""
        project = make_project()
        project.tenant_id = uuid.uuid4()  # different tenant
        override_db.get.return_value = project

        resp = await client.get(f"/api/v1/projects/{PROJECT_ID}")
        assert resp.status_code == 404


class TestUpdateProject:
    @pytest.mark.asyncio
    async def test_tm_can_patch_project(self, client, as_tm, override_db, make_project):
        project = make_project()
        override_db.get.return_value = project
        override_db.refresh.side_effect = lambda obj: None

        resp = await client.patch(
            f"/api/v1/projects/{PROJECT_ID}",
            json={"name": "Renamed Project"},
        )
        assert resp.status_code == 200


class TestDeleteProject:
    @pytest.mark.asyncio
    async def test_admin_can_delete_project(self, client, as_admin, override_db, make_project):
        project = make_project()
        override_db.get.return_value = project

        resp = await client.delete(f"/api/v1/projects/{PROJECT_ID}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client, as_admin, override_db):
        override_db.get.return_value = None

        resp = await client.delete(f"/api/v1/projects/{PROJECT_ID}")
        assert resp.status_code == 404
