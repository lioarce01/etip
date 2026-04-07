"""Integration tests — /api/v1/analytics endpoint."""

import uuid
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from etip_api.models.employee import Employee
from etip_api.models.project import Project
from etip_api.models.recommendation import Recommendation
from etip_api.auth.jwt import create_access_token
from tests.integration.conftest import auth, register


async def _seed_employee(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    email: str,
    full_name: str,
) -> Employee:
    """Create an employee for seeding tests."""
    emp = Employee(
        tenant_id=tenant_id,
        email=email,
        full_name=full_name,
        is_active=True,
    )
    db.add(emp)
    await db.flush()
    await db.refresh(emp)
    return emp


async def _seed_project(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    name: str,
) -> Project:
    """Create a project for seeding tests."""
    proj = Project(
        tenant_id=tenant_id,
        name=name,
    )
    db.add(proj)
    await db.flush()
    await db.refresh(proj)
    return proj


async def _seed_recommendation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    employee_id: uuid.UUID,
    *,
    score: float = 0.9,
    feedback: str | None = None,
) -> Recommendation:
    """Create a recommendation for seeding tests."""
    rec = Recommendation(
        tenant_id=tenant_id,
        project_id=project_id,
        employee_id=employee_id,
        score=score,
        feedback=feedback,
    )
    db.add(rec)
    await db.flush()
    await db.refresh(rec)
    return rec


class TestAnalyticsIntegration:
    async def test_analytics_returns_200(self, client: AsyncClient):
        """Analytics endpoint returns 200 with all fields."""
        token, _ = await register(client)

        resp = await client.get("/api/v1/analytics", headers=auth(token))
        assert resp.status_code == 200

        body = resp.json()
        assert "total_employees" in body
        assert "total_projects" in body
        assert "total_recommendations" in body
        assert "accepted_count" in body
        assert "rejected_count" in body
        assert "maybe_count" in body
        assert "no_feedback_count" in body
        assert "precision_at_5" in body
        assert "precision_at_10" in body
        assert "acceptance_rate" in body

    async def test_analytics_multi_tenant_isolation(self, client: AsyncClient, db: AsyncSession):
        """Two tenants see only their own analytics."""
        # Register two tenants
        token1, tenant_id1 = await register(
            client, slug="tenant-1", email="admin@t1.com", company_name="Tenant 1"
        )
        token2, tenant_id2 = await register(
            client, slug="tenant-2", email="admin@t2.com", company_name="Tenant 2"
        )
        tenant_uuid_1 = uuid.UUID(tenant_id1)
        tenant_uuid_2 = uuid.UUID(tenant_id2)

        # Seed data for tenant 1
        emp1 = await _seed_employee(db, tenant_uuid_1, email="emp1@t1.com", full_name="Employee 1")
        proj1 = await _seed_project(db, tenant_uuid_1, name="T1 Project")
        await _seed_recommendation(db, tenant_uuid_1, proj1.id, emp1.id, feedback="accepted")
        await db.commit()

        # Seed data for tenant 2
        emp2 = await _seed_employee(db, tenant_uuid_2, email="emp2@t2.com", full_name="Employee 2")
        proj2 = await _seed_project(db, tenant_uuid_2, name="T2 Project")
        await _seed_recommendation(db, tenant_uuid_2, proj2.id, emp2.id, feedback="rejected")
        await db.commit()

        # Tenant 1 should see 1 accepted, 0 rejected
        resp1 = await client.get("/api/v1/analytics", headers=auth(token1))
        assert resp1.status_code == 200
        body1 = resp1.json()
        assert body1["accepted_count"] == 1
        assert body1["rejected_count"] == 0

        # Tenant 2 should see 0 accepted, 1 rejected
        resp2 = await client.get("/api/v1/analytics", headers=auth(token2))
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert body2["accepted_count"] == 0
        assert body2["rejected_count"] == 1

    async def test_analytics_counts_feedback_correctly(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Analytics counts all feedback categories correctly."""
        token, tenant_id = await register(client)
        tenant_uuid = uuid.UUID(tenant_id)

        # Seed data
        proj = await _seed_project(db, tenant_uuid, name="Test Project")

        # Create different employees for each recommendation
        emp1 = await _seed_employee(db, tenant_uuid, email="emp1@test.com", full_name="Employee 1")
        emp2 = await _seed_employee(db, tenant_uuid, email="emp2@test.com", full_name="Employee 2")
        emp3 = await _seed_employee(db, tenant_uuid, email="emp3@test.com", full_name="Employee 3")
        emp4 = await _seed_employee(db, tenant_uuid, email="emp4@test.com", full_name="Employee 4")
        emp5 = await _seed_employee(db, tenant_uuid, email="emp5@test.com", full_name="Employee 5")
        emp6 = await _seed_employee(db, tenant_uuid, email="emp6@test.com", full_name="Employee 6")
        emp7 = await _seed_employee(db, tenant_uuid, email="emp7@test.com", full_name="Employee 7")

        # Create 3 accepted, 2 rejected, 1 maybe, 1 no_feedback
        await _seed_recommendation(db, tenant_uuid, proj.id, emp1.id, score=0.9, feedback="accepted")
        await _seed_recommendation(db, tenant_uuid, proj.id, emp2.id, score=0.8, feedback="accepted")
        await _seed_recommendation(db, tenant_uuid, proj.id, emp3.id, score=0.7, feedback="accepted")
        await _seed_recommendation(db, tenant_uuid, proj.id, emp4.id, score=0.6, feedback="rejected")
        await _seed_recommendation(db, tenant_uuid, proj.id, emp5.id, score=0.5, feedback="rejected")
        await _seed_recommendation(db, tenant_uuid, proj.id, emp6.id, score=0.4, feedback="maybe")
        await _seed_recommendation(db, tenant_uuid, proj.id, emp7.id, score=0.3, feedback=None)
        await db.commit()

        resp = await client.get("/api/v1/analytics", headers=auth(token))
        assert resp.status_code == 200

        body = resp.json()
        assert body["total_recommendations"] == 7
        assert body["accepted_count"] == 3
        assert body["rejected_count"] == 2
        assert body["maybe_count"] == 1
        assert body["no_feedback_count"] == 1
        # acceptance_rate = 3 / (3 + 2 + 1) = 3 / 6 = 0.5
        assert body["acceptance_rate"] == 0.5

    async def test_analytics_empty_tenant_zeros_out(self, client: AsyncClient):
        """Fresh tenant with no data returns all zeros."""
        token, _ = await register(client)

        resp = await client.get("/api/v1/analytics", headers=auth(token))
        assert resp.status_code == 200

        body = resp.json()
        assert body["total_employees"] == 0
        assert body["total_projects"] == 0
        assert body["total_recommendations"] == 0
        assert body["accepted_count"] == 0
        assert body["rejected_count"] == 0
        assert body["maybe_count"] == 0
        assert body["no_feedback_count"] == 0
        assert body["precision_at_5"] == 0.0
        assert body["precision_at_10"] == 0.0
        assert body["acceptance_rate"] == 0.0
