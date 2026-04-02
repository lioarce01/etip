"""Tests for /api/v1/employees router."""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etip_api.models.employee import Employee
from tests.conftest import EMPLOYEE_ID, TENANT_ID


class TestListEmployees:
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
        await client.get("/api/v1/employees")

        compiled = captured[1].compile(dialect=pg_dialect())
        assert "tenant_id" in str(compiled)

    @pytest.mark.asyncio
    async def test_search_escapes_like_metacharacters(self, client, as_tm, override_db):
        """Search with % and _ must not cause a pattern-injection DoS."""
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
        await client.get("/api/v1/employees?search=100%25_done")

        # Both count and item queries must exist
        assert call_count == 2
        # The compiled SQL must contain the escaped literal, not raw metacharacters
        compiled = captured[1].compile(dialect=pg_dialect())
        sql = str(compiled)
        assert "tenant_id" in sql

    @pytest.mark.asyncio
    async def test_returns_paginated_list(self, client, as_tm, override_db, make_employee):
        emp = make_employee()
        mock_count = MagicMock()
        mock_count.scalar_one.return_value = 1
        mock_items = MagicMock()
        mock_items.scalars.return_value.all.return_value = [emp]
        override_db.execute.side_effect = [mock_count, mock_items]

        resp = await client.get("/api/v1/employees")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["email"] == "dev@acme.com"

    @pytest.mark.asyncio
    async def test_returns_employee_skills(self, client, as_tm, override_db, make_employee):
        emp = make_employee(skills=["Python", "FastAPI"])
        mock_count = MagicMock()
        mock_count.scalar_one.return_value = 1
        mock_items = MagicMock()
        mock_items.scalars.return_value.all.return_value = [emp]
        override_db.execute.side_effect = [mock_count, mock_items]

        resp = await client.get("/api/v1/employees")
        skills = resp.json()["items"][0]["skills"]
        labels = [s["preferred_label"] for s in skills]
        assert "Python" in labels
        assert "FastAPI" in labels

    @pytest.mark.asyncio
    async def test_page_size_respected(self, client, as_tm, override_db, make_employee):
        mock_count = MagicMock()
        mock_count.scalar_one.return_value = 0
        mock_items = MagicMock()
        mock_items.scalars.return_value.all.return_value = []
        override_db.execute.side_effect = [mock_count, mock_items]

        resp = await client.get("/api/v1/employees?page_size=5")
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 5


class TestGetEmployee:
    @pytest.mark.asyncio
    async def test_returns_employee_by_id(self, client, as_tm, override_db, make_employee):
        emp = make_employee()
        override_db.get.return_value = emp

        resp = await client.get(f"/api/v1/employees/{EMPLOYEE_ID}")
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Juan Pérez"

    @pytest.mark.asyncio
    async def test_inactive_employee_returns_404(self, client, as_tm, override_db, make_employee):
        emp = make_employee()
        emp.is_active = False
        override_db.get.return_value = emp

        resp = await client.get(f"/api/v1/employees/{EMPLOYEE_ID}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_employee_returns_404(self, client, as_tm, override_db):
        override_db.get.return_value = None

        resp = await client.get(f"/api/v1/employees/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_employee_returns_404(self, client, as_tm, override_db, make_employee):
        """An employee belonging to a different tenant must be invisible."""
        emp = make_employee()
        emp.tenant_id = uuid.uuid4()  # different tenant
        override_db.get.return_value = emp

        resp = await client.get(f"/api/v1/employees/{EMPLOYEE_ID}")
        assert resp.status_code == 404


class TestMyProfile:
    @pytest.mark.asyncio
    async def test_returns_linked_employee_profile(self, client, as_tm, override_db, make_employee, make_user):
        emp = make_employee()
        override_db.get.return_value = emp

        resp = await client.get("/api/v1/employees/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == "dev@acme.com"

    @pytest.mark.asyncio
    async def test_user_without_employee_link_returns_404(self, client, as_tm, override_db, make_user):
        # Override the user to have no employee_id
        user = make_user(role="tm", employee_id=None)
        from etip_api.auth.dependencies import get_current_user
        from etip_api.main import app

        async def _no_link_user():
            return user

        app.dependency_overrides[get_current_user] = _no_link_user

        resp = await client.get("/api/v1/employees/me")
        assert resp.status_code == 404


class TestGetAvailability:
    @pytest.mark.asyncio
    async def test_returns_availability_for_valid_employee(
        self, client, as_tm, override_db, make_employee
    ):
        emp = make_employee()
        override_db.get.return_value = emp

        mock_alloc = MagicMock()
        mock_alloc.scalar_one.return_value = 40.0
        override_db.execute.return_value = mock_alloc

        resp = await client.get(
            f"/api/v1/employees/{EMPLOYEE_ID}/availability"
            "?start_date=2026-04-01&end_date=2026-06-30"
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["allocated_pct"] == 40.0
        assert body["availability_pct"] == 60.0

    @pytest.mark.asyncio
    async def test_missing_dates_returns_422(self, client, as_tm, override_db):
        resp = await client.get(f"/api/v1/employees/{EMPLOYEE_ID}/availability")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_availability_query_scoped_to_tenant(
        self, client, as_tm, override_db, make_employee
    ):
        """Allocation query must include a tenant_id WHERE clause to prevent cross-tenant leakage."""
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        emp = make_employee()
        override_db.get.return_value = emp

        captured_stmt = {}

        mock_alloc = MagicMock()
        mock_alloc.scalar_one.return_value = 0.0

        async def _capturing_execute(stmt, *args, **kwargs):
            captured_stmt["stmt"] = stmt
            return mock_alloc

        override_db.execute = _capturing_execute

        resp = await client.get(
            f"/api/v1/employees/{EMPLOYEE_ID}/availability"
            "?start_date=2026-04-01&end_date=2026-06-30"
        )

        assert resp.status_code == 200
        compiled = captured_stmt["stmt"].compile(dialect=pg_dialect())
        assert "tenant_id" in str(compiled)


class TestImportEmployeesCsv:
    def _file(self, content: str) -> dict:
        return {"file": ("employees.csv", content.encode("utf-8"), "text/csv")}

    def _bad_bytes(self) -> dict:
        return {"file": ("employees.csv", b"\xff\xfe invalid bytes", "text/csv")}

    def _mock_new(self) -> MagicMock:
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        return r

    def _mock_existing(self, emp) -> MagicMock:
        r = MagicMock()
        r.scalar_one_or_none.return_value = emp
        return r

    @pytest.mark.asyncio
    async def test_creates_new_employees(self, client, as_admin, override_db):
        override_db.execute.return_value = self._mock_new()

        with patch("etip_api.routers.employees.log_action", new=AsyncMock()):
            resp = await client.post(
                "/api/v1/employees/import/csv",
                files=self._file(
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

    @pytest.mark.asyncio
    async def test_updates_existing_employee(self, client, as_admin, override_db, make_employee):
        existing = make_employee()
        override_db.execute.return_value = self._mock_existing(existing)

        with patch("etip_api.routers.employees.log_action", new=AsyncMock()):
            resp = await client.post(
                "/api/v1/employees/import/csv",
                files=self._file("email,full_name\ndev@acme.com,Dev Updated\n"),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 0
        assert body["updated"] == 1
        assert existing.full_name == "Dev Updated"

    @pytest.mark.asyncio
    async def test_mixed_create_and_update(self, client, as_admin, override_db, make_employee):
        existing = make_employee()
        override_db.execute.side_effect = [
            self._mock_existing(existing),
            self._mock_new(),
        ]

        with patch("etip_api.routers.employees.log_action", new=AsyncMock()):
            resp = await client.post(
                "/api/v1/employees/import/csv",
                files=self._file(
                    "email,full_name\n"
                    "dev@acme.com,Existing Dev\n"
                    "new@acme.com,New Person\n"
                ),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 1
        assert body["updated"] == 1

    @pytest.mark.asyncio
    async def test_row_missing_email_reported_as_error(self, client, as_admin, override_db):
        override_db.execute.return_value = self._mock_new()

        with patch("etip_api.routers.employees.log_action", new=AsyncMock()):
            resp = await client.post(
                "/api/v1/employees/import/csv",
                files=self._file(
                    "email,full_name\n"
                    ",No Email Here\n"      # row 2 — error
                    "alice@acme.com,Alice\n"  # row 3 — created
                ),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 1
        assert len(body["errors"]) == 1
        assert "Row 2" in body["errors"][0]

    @pytest.mark.asyncio
    async def test_row_missing_full_name_reported_as_error(self, client, as_admin, override_db):
        override_db.execute.return_value = self._mock_new()

        with patch("etip_api.routers.employees.log_action", new=AsyncMock()):
            resp = await client.post(
                "/api/v1/employees/import/csv",
                files=self._file("email,full_name\nalice@acme.com,\n"),
            )

        assert resp.status_code == 200
        assert len(resp.json()["errors"]) == 1

    @pytest.mark.asyncio
    async def test_missing_required_columns_returns_422(self, client, as_admin, override_db):
        resp = await client.post(
            "/api/v1/employees/import/csv",
            files=self._file("name,department\nAlice,Engineering\n"),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_non_utf8_file_returns_400(self, client, as_admin, override_db):
        resp = await client.post(
            "/api/v1/employees/import/csv",
            files=self._bad_bytes(),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_new_employee_gets_caller_tenant_id(self, client, as_admin, override_db):
        override_db.execute.return_value = self._mock_new()
        added: list = []
        override_db.add = lambda obj: added.append(obj)

        with patch("etip_api.routers.employees.log_action", new=AsyncMock()):
            await client.post(
                "/api/v1/employees/import/csv",
                files=self._file("email,full_name\nnew@acme.com,New Person\n"),
            )

        employees = [o for o in added if isinstance(o, Employee)]
        assert len(employees) == 1
        assert employees[0].tenant_id == TENANT_ID

    @pytest.mark.asyncio
    async def test_audit_log_called_after_import(self, client, as_admin, override_db):
        override_db.execute.return_value = self._mock_new()

        with patch("etip_api.routers.employees.log_action", new=AsyncMock()) as mock_log:
            await client.post(
                "/api/v1/employees/import/csv",
                files=self._file("email,full_name\nalice@acme.com,Alice\n"),
            )

        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs["action"] == "employees.csv_import"

    @pytest.mark.asyncio
    async def test_optional_fields_default_to_none(self, client, as_admin, override_db):
        override_db.execute.return_value = self._mock_new()
        added: list = []
        override_db.add = lambda obj: added.append(obj)

        with patch("etip_api.routers.employees.log_action", new=AsyncMock()):
            await client.post(
                "/api/v1/employees/import/csv",
                files=self._file("email,full_name\nalice@acme.com,Alice\n"),
            )

        emp = next(o for o in added if isinstance(o, Employee))
        assert emp.title is None
        assert emp.department is None
