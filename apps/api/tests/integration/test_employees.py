"""Integration tests — /api/v1/employees endpoints.

Employees are created via sync worker, not the API. We seed them directly via DB.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from etip_api.auth.jwt import create_access_token
from etip_api.models.employee import Employee
from tests.integration.conftest import auth, register


def _csv(content: str) -> dict:
    return {"file": ("employees.csv", content.encode("utf-8"), "text/csv")}


async def _seed_employee(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    email: str = "dev@acme.com",
    full_name: str = "Jane Dev",
    department: str = "Engineering",
    is_active: bool = True,
) -> Employee:
    emp = Employee(
        tenant_id=tenant_id,
        email=email,
        full_name=full_name,
        department=department,
        is_active=is_active,
        external_ids={},
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


class TestListEmployees:
    async def test_empty_list_returns_200(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.get("/api/v1/employees", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_returns_seeded_employees(self, client: AsyncClient, db: AsyncSession):
        token, tenant_id = await register(client)
        await _seed_employee(db, uuid.UUID(tenant_id), email="e1@acme.com", full_name="Alice")
        await _seed_employee(db, uuid.UUID(tenant_id), email="e2@acme.com", full_name="Bob")

        resp = await client.get("/api/v1/employees", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_scoped_to_tenant(self, client: AsyncClient, db: AsyncSession):
        token1, tid1 = await register(client, slug="tenant-one", email="admin@tenant-one.com", company_name="Tenant One")
        token2, tid2 = await register(client, slug="tenant-two", email="admin@tenant-two.com", company_name="Tenant Two")

        await _seed_employee(db, uuid.UUID(tid1), email="emp@t1.com")
        await _seed_employee(db, uuid.UUID(tid1), email="emp2@t1.com")

        resp = await client.get("/api/v1/employees", headers=auth(token2))
        assert resp.json()["total"] == 0

    async def test_search_by_name(self, client: AsyncClient, db: AsyncSession):
        token, tenant_id = await register(client)
        await _seed_employee(db, uuid.UUID(tenant_id), full_name="Alice Smith", email="alice@acme.com")
        await _seed_employee(db, uuid.UUID(tenant_id), full_name="Bob Jones", email="bob@acme.com")

        resp = await client.get("/api/v1/employees?search=alice", headers=auth(token))
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["full_name"] == "Alice Smith"

    async def test_search_by_email(self, client: AsyncClient, db: AsyncSession):
        token, tenant_id = await register(client)
        await _seed_employee(db, uuid.UUID(tenant_id), full_name="Alice", email="unique@acme.com")
        await _seed_employee(db, uuid.UUID(tenant_id), full_name="Bob", email="other@acme.com")

        resp = await client.get("/api/v1/employees?search=unique", headers=auth(token))
        assert resp.json()["total"] == 1

    async def test_filter_by_department(self, client: AsyncClient, db: AsyncSession):
        token, tenant_id = await register(client)
        await _seed_employee(db, uuid.UUID(tenant_id), email="e@eng.com", department="Engineering")
        await _seed_employee(db, uuid.UUID(tenant_id), email="d@design.com", department="Design")

        resp = await client.get("/api/v1/employees?department=Engineering", headers=auth(token))
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["department"] == "Engineering"

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

        resp = await client.get("/api/v1/employees", headers=auth(dev_token))
        assert resp.status_code == 403

    async def test_inactive_employees_excluded(self, client: AsyncClient, db: AsyncSession):
        token, tenant_id = await register(client)
        await _seed_employee(db, uuid.UUID(tenant_id), email="active@acme.com", is_active=True)
        await _seed_employee(db, uuid.UUID(tenant_id), email="inactive@acme.com", is_active=False)

        resp = await client.get("/api/v1/employees", headers=auth(token))
        assert resp.json()["total"] == 1


class TestGetEmployee:
    async def test_returns_employee_by_id(self, client: AsyncClient, db: AsyncSession):
        token, tenant_id = await register(client)
        emp = await _seed_employee(db, uuid.UUID(tenant_id), full_name="Jane Dev")

        resp = await client.get(f"/api/v1/employees/{emp.id}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Jane Dev"

    async def test_nonexistent_returns_404(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.get(f"/api/v1/employees/{uuid.uuid4()}", headers=auth(token))
        assert resp.status_code == 404

    async def test_cross_tenant_returns_404(self, client: AsyncClient, db: AsyncSession):
        token1, tid1 = await register(client, slug="tenant-one", email="admin@tenant-one.com", company_name="Tenant One")
        _, tid2 = await register(client, slug="tenant-two", email="admin@tenant-two.com", company_name="Tenant Two")

        emp = await _seed_employee(db, uuid.UUID(tid2), email="emp@t2.com")

        resp = await client.get(f"/api/v1/employees/{emp.id}", headers=auth(token1))
        assert resp.status_code == 404


class TestGetMyProfile:
    async def test_no_employee_linked_returns_404(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.get("/api/v1/employees/me", headers=auth(token))
        assert resp.status_code == 404


class TestGetAvailability:
    async def test_returns_availability(self, client: AsyncClient, db: AsyncSession):
        token, tenant_id = await register(client)
        emp = await _seed_employee(db, uuid.UUID(tenant_id))

        resp = await client.get(
            f"/api/v1/employees/{emp.id}/availability?start_date=2026-04-01&end_date=2026-04-30",
            headers=auth(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["capacity_pct"] == 100.0
        assert body["availability_pct"] == 100.0
        assert body["allocated_pct"] == 0.0

    async def test_missing_dates_returns_422(self, client: AsyncClient, db: AsyncSession):
        token, tenant_id = await register(client)
        emp = await _seed_employee(db, uuid.UUID(tenant_id))

        resp = await client.get(
            f"/api/v1/employees/{emp.id}/availability",
            headers=auth(token),
        )
        assert resp.status_code == 422


class TestImportEmployeesCsv:
    async def test_admin_imports_new_employees(self, client: AsyncClient, db: AsyncSession):
        token, _ = await register(client)

        resp = await client.post(
            "/api/v1/employees/import/csv",
            headers=auth(token),
            files=_csv(
                "email,full_name,title,department\n"
                "alice@acme.com,Alice Smith,Engineer,Engineering\n"
                "bob@acme.com,Bob Jones,Lead,Platform\n"
            ),
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 2
        assert body["updated"] == 0
        assert body["errors"] == []

    async def test_import_updates_existing_employee(self, client: AsyncClient, db: AsyncSession):
        token, tenant_id = await register(client)
        await _seed_employee(db, uuid.UUID(tenant_id), email="alice@acme.com", full_name="Alice Old")

        resp = await client.post(
            "/api/v1/employees/import/csv",
            headers=auth(token),
            files=_csv("email,full_name,title\nalice@acme.com,Alice New,Senior Engineer\n"),
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 0
        assert body["updated"] == 1

        # Verify the update persisted
        list_resp = await client.get("/api/v1/employees", headers=auth(token))
        assert list_resp.json()["items"][0]["full_name"] == "Alice New"

    async def test_import_scoped_to_caller_tenant(self, client: AsyncClient, db: AsyncSession):
        token1, _ = await register(client, slug="t1", email="admin@t1.com", company_name="T1")
        token2, _ = await register(client, slug="t2", email="admin@t2.com", company_name="T2")

        await client.post(
            "/api/v1/employees/import/csv",
            headers=auth(token1),
            files=_csv("email,full_name\nonly@t1.com,Only T1\n"),
        )

        # T2 must not see T1's employees
        resp = await client.get("/api/v1/employees", headers=auth(token2))
        assert resp.json()["total"] == 0

    async def test_non_admin_cannot_import(self, client: AsyncClient, db: AsyncSession):
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
            "/api/v1/employees/import/csv",
            headers=auth(tm_token),
            files=_csv("email,full_name\nemp@acme.com,Employee\n"),
        )
        assert resp.status_code == 403

    async def test_missing_columns_returns_422(self, client: AsyncClient, db: AsyncSession):
        token, _ = await register(client)

        resp = await client.post(
            "/api/v1/employees/import/csv",
            headers=auth(token),
            files=_csv("name,department\nAlice,Engineering\n"),
        )
        assert resp.status_code == 422

    async def test_rows_with_missing_required_fields_are_errors(
        self, client: AsyncClient, db: AsyncSession
    ):
        token, _ = await register(client)

        resp = await client.post(
            "/api/v1/employees/import/csv",
            headers=auth(token),
            files=_csv(
                "email,full_name\n"
                ",No Email\n"            # row 2 — error
                "alice@acme.com,Alice\n"  # row 3 — created
            ),
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 1
        assert len(body["errors"]) == 1
        assert "Row 2" in body["errors"][0]

    async def test_non_utf8_file_returns_400(self, client: AsyncClient, db: AsyncSession):
        token, _ = await register(client)

        resp = await client.post(
            "/api/v1/employees/import/csv",
            headers=auth(token),
            files={"file": ("employees.csv", b"\xff\xfe bad bytes", "text/csv")},
        )
        assert resp.status_code == 400

    async def test_unauthenticated_returns_401(self, client: AsyncClient, db: AsyncSession):
        resp = await client.post(
            "/api/v1/employees/import/csv",
            files=_csv("email,full_name\nalice@acme.com,Alice\n"),
        )
        assert resp.status_code in (401, 403)
