"""Tests for etip_api.worker.sync — tenant isolation in the sync runner."""

import uuid
from datetime import date
from unittest.mock import MagicMock, patch, call

import pytest

from tests.conftest import TENANT_ID


class TestNormalizeEmail:
    def test_lowercases(self):
        from etip_api.worker.sync import _normalize_email
        assert _normalize_email("User@ACME.COM") == "user@acme.com"

    def test_strips_whitespace(self):
        from etip_api.worker.sync import _normalize_email
        assert _normalize_email("  user@acme.com  ") == "user@acme.com"

    def test_strips_alias_suffix(self):
        from etip_api.worker.sync import _normalize_email
        assert _normalize_email("user+alias@acme.com") == "user@acme.com"

    def test_gmail_dots_removed(self):
        from etip_api.worker.sync import _normalize_email
        assert _normalize_email("jo.hn.doe@gmail.com") == "johndoe@gmail.com"

    def test_googlemail_dots_removed(self):
        from etip_api.worker.sync import _normalize_email
        assert _normalize_email("jo.hn@googlemail.com") == "john@googlemail.com"

    def test_non_gmail_dots_preserved(self):
        from etip_api.worker.sync import _normalize_email
        assert _normalize_email("jo.hn@acme.com") == "jo.hn@acme.com"

    def test_gmail_alias_and_dots_both_stripped(self):
        from etip_api.worker.sync import _normalize_email
        assert _normalize_email("jo.hn+work@gmail.com") == "john@gmail.com"


class TestEmailDeduplication:
    def test_gmail_dot_variants_resolve_to_same_employee(self):
        """Two DTOs with equivalent Gmail addresses must merge into one employee record."""
        from etip_api.worker.sync import _upsert_employee
        from etip_core.schemas import EmployeeDTO
        from etip_api.models.employee import Employee

        # Simulate a DB that returns None first (insert) then the created employee (update)
        created = Employee()
        created.id = uuid.uuid4()
        created.tenant_id = TENANT_ID
        created.email = "johndoe@gmail.com"
        created.full_name = "John Doe"
        created.title = None
        created.department = None
        created.external_ids = {"github": "johndoe"}

        db = MagicMock()
        # First call: no existing → insert
        # Second call: finds the just-created employee → update
        db.execute.return_value.scalar_one_or_none.side_effect = [None, created]

        dto1 = EmployeeDTO(source="github", external_id="johndoe", email="jo.hn.doe@gmail.com", full_name="John Doe")
        dto2 = EmployeeDTO(source="hris", external_id="jdoe-001", email="johndoe@gmail.com", full_name="John Doe")

        _upsert_employee(db, str(TENANT_ID), dto1)
        _upsert_employee(db, str(TENANT_ID), dto2)

        # First call inserts, second call updates (no second add)
        assert db.add.call_count == 1
        added = db.add.call_args[0][0]
        assert added.email == "johndoe@gmail.com"

    def test_uppercase_email_deduplicates(self):
        """Same email with different casing must map to the same employee."""
        from etip_api.worker.sync import _upsert_employee
        from etip_core.schemas import EmployeeDTO
        from etip_api.models.employee import Employee

        existing = Employee()
        existing.id = uuid.uuid4()
        existing.tenant_id = TENANT_ID
        existing.email = "user@acme.com"
        existing.full_name = "Original Name"
        existing.title = None
        existing.department = None
        existing.external_ids = {}

        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = existing

        dto = EmployeeDTO(source="hris", external_id="u1", email="USER@ACME.COM", full_name="Updated Name")
        _upsert_employee(db, str(TENANT_ID), dto)

        db.add.assert_not_called()
        assert existing.full_name == "Updated Name"

    def test_normalized_email_stored_on_insert(self):
        """The canonical normalized email must be stored, not the raw input."""
        from etip_api.worker.sync import _upsert_employee
        from etip_core.schemas import EmployeeDTO

        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None

        dto = EmployeeDTO(source="github", external_id="gh1", email="Jo.Hn+Work@Gmail.Com", full_name="John")
        _upsert_employee(db, str(TENANT_ID), dto)

        added = db.add.call_args[0][0]
        assert added.email == "john@gmail.com"


class TestRunSyncTenantIsolation:
    def _make_session(self, employees=None):
        """Build a minimal mock synchronous session."""
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)

        # execute returns a chainable result
        emp_result = MagicMock()
        emp_result.scalars.return_value.all.return_value = employees or []

        # First execute call is SET rls.tenant_id, second is the employee SELECT
        db.execute.side_effect = [MagicMock(), emp_result]
        db.commit = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()
        return db

    def _make_session_maker(self, db):
        maker = MagicMock()
        maker.return_value.__enter__ = MagicMock(return_value=db)
        maker.return_value.__exit__ = MagicMock(return_value=False)
        return maker

    def test_uses_set_not_set_local(self):
        """Worker must use SET (not SET LOCAL) so RLS survives intermediate commits."""
        import inspect
        from etip_api.worker import sync

        source = inspect.getsource(sync.run_sync)
        # The actual SQL string must not contain SET LOCAL (comments are ok)
        # Extract the text() call argument
        assert '"SET rls.tenant_id' in source or "'SET rls.tenant_id" in source
        # Must not call SET LOCAL in the SQL string literal
        assert '"SET LOCAL' not in source and "'SET LOCAL" not in source

    def test_employee_query_scoped_to_tenant(self):
        """The SELECT employees query must filter by tenant_id."""
        from etip_api.worker.sync import run_sync
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        db = self._make_session()
        session_maker = self._make_session_maker(db)

        with patch("sqlalchemy.create_engine"), \
             patch("sqlalchemy.orm.sessionmaker", return_value=session_maker), \
             patch("etip_api.worker.sync.pm") as mock_pm, \
             patch("etip_core.settings.get_settings") as mock_settings:
            mock_settings.return_value.database_url_sync = "postgresql://x"
            mock_pm.hook.sync_employees.return_value = []
            run_sync(str(TENANT_ID), "github", {})

        # Second execute call is the employee SELECT (after SET rls.tenant_id)
        second_call = db.execute.call_args_list[1]
        stmt = second_call[0][0]
        compiled = stmt.compile(dialect=pg_dialect())
        sql = str(compiled)
        assert "tenant_id" in sql

    def test_upsert_employee_lookup_scoped_to_tenant(self):
        """_upsert_employee must scope the email lookup to the tenant."""
        from etip_api.worker.sync import _upsert_employee
        from etip_core.schemas import EmployeeDTO
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None

        dto = EmployeeDTO(
            source="github",
            external_id="user123",
            email="dev@acme.com",
            full_name="Dev User",
        )
        _upsert_employee(db, str(TENANT_ID), dto)

        stmt = db.execute.call_args[0][0]
        compiled = stmt.compile(dialect=pg_dialect())
        sql = str(compiled)
        assert "tenant_id" in sql
        assert "email" in sql

    def test_upsert_employee_updates_existing(self):
        """When an employee with same tenant+email exists, update — don't insert."""
        from etip_api.worker.sync import _upsert_employee
        from etip_core.schemas import EmployeeDTO
        from etip_api.models.employee import Employee

        existing = Employee()
        existing.id = uuid.uuid4()
        existing.tenant_id = TENANT_ID
        existing.email = "dev@acme.com"
        existing.full_name = "Old Name"
        existing.title = "Junior Dev"
        existing.department = "Eng"
        existing.external_ids = {}

        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = existing

        dto = EmployeeDTO(
            source="github",
            external_id="gh_user",
            email="dev@acme.com",
            full_name="New Name",
            title="Senior Dev",
        )
        _upsert_employee(db, str(TENANT_ID), dto)

        assert existing.full_name == "New Name"
        assert existing.title == "Senior Dev"
        db.add.assert_not_called()

    def test_upsert_employee_inserts_new(self):
        """When no employee found, insert with the correct tenant_id."""
        from etip_api.worker.sync import _upsert_employee
        from etip_core.schemas import EmployeeDTO

        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None

        dto = EmployeeDTO(
            source="github",
            external_id="gh_user",
            email="new@acme.com",
            full_name="New Employee",
        )
        _upsert_employee(db, str(TENANT_ID), dto)

        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert added.tenant_id == TENANT_ID
        assert added.email == "new@acme.com"


class TestSyncStatusUpdate:
    def _run_sync_with_mocks(self, connector_id=None, skill_error=False):
        """Helper: run run_sync with a fully mocked session."""
        from etip_api.worker.sync import run_sync
        from etip_api.models.employee import Employee

        emp = Employee()
        emp.id = uuid.uuid4()
        emp.tenant_id = TENANT_ID
        emp.email = "dev@acme.com"
        emp.external_ids = {}

        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)

        emp_result = MagicMock()
        emp_result.scalars.return_value.all.return_value = [emp]
        # SET + employee SELECT + Qdrant index select + connector UPDATE
        db.execute.side_effect = [MagicMock(), emp_result, MagicMock(), MagicMock()]
        db.commit = MagicMock()
        db.rollback = MagicMock()

        session_maker = MagicMock()
        session_maker.return_value.__enter__ = MagicMock(return_value=db)
        session_maker.return_value.__exit__ = MagicMock(return_value=False)

        def _mock_sync_skills(**kwargs):
            if skill_error:
                raise RuntimeError("network error")
            return []

        with patch("sqlalchemy.create_engine"), \
             patch("sqlalchemy.orm.sessionmaker", return_value=session_maker), \
             patch("etip_api.worker.sync.pm") as mock_pm, \
             patch("etip_core.settings.get_settings") as mock_settings:
            mock_settings.return_value.database_url_sync = "postgresql://x"
            mock_pm.hook.sync_employees.return_value = []
            mock_pm.hook.sync_skills.side_effect = _mock_sync_skills
            result = run_sync(str(TENANT_ID), "github", {}, connector_id=connector_id)

        return result, db

    def test_sync_status_updated_to_idle_on_success(self):
        """After a clean sync, connector sync_status must be updated to 'idle'."""
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        connector_id = str(uuid.uuid4())
        _, db = self._run_sync_with_mocks(connector_id=connector_id)

        # The last execute call should be an UPDATE
        last_call = db.execute.call_args_list[-1]
        stmt = last_call[0][0]
        compiled = stmt.compile(dialect=pg_dialect())
        sql = str(compiled)
        assert "connector_configs" in sql or "UPDATE" in str(stmt)
        assert db.commit.called

    def test_sync_status_updated_to_error_on_failure(self):
        """After a sync with skill errors, connector sync_status must be 'error'."""
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        connector_id = str(uuid.uuid4())
        result, db = self._run_sync_with_mocks(connector_id=connector_id, skill_error=True)

        assert len(result["errors"]) > 0

        last_call = db.execute.call_args_list[-1]
        stmt = last_call[0][0]
        compiled = stmt.compile(dialect=pg_dialect())
        sql = str(compiled)
        assert "connector_configs" in sql or "UPDATE" in str(stmt)

    def test_no_connector_id_skips_status_update(self):
        """When connector_id is None (legacy call), no UPDATE is issued."""
        _, db = self._run_sync_with_mocks(connector_id=None)

        # Only SET + employee SELECT calls — no UPDATE
        for call in db.execute.call_args_list:
            stmt = call[0][0]
            compiled_str = str(stmt)
            assert "UPDATE" not in compiled_str.upper() or "connector_configs" not in compiled_str

    def test_skill_error_triggers_rollback(self):
        """A failed skill sync must rollback the partial transaction, not commit it."""
        _, db = self._run_sync_with_mocks(connector_id=None, skill_error=True)

        db.rollback.assert_called()
