"""
Root conftest — shared fixtures available to all test modules.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from etip_api.models.employee import Employee
from etip_api.models.project import Project
from etip_api.models.skill import EmployeeSkill, Skill
from etip_api.models.user import User


# ── Canonical UUIDs used across tests ─────────────────────────────────────────

TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
EMPLOYEE_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
PROJECT_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")
SKILL_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")


# ── Model factories ────────────────────────────────────────────────────────────

@pytest.fixture
def tenant_id() -> uuid.UUID:
    return TENANT_ID


@pytest.fixture
def make_user():
    def _make(
        role: str = "tm",
        user_id: uuid.UUID = USER_ID,
        tenant_id: uuid.UUID = TENANT_ID,
        hashed_password: str = "$2b$12$placeholder",
        employee_id: uuid.UUID | None = EMPLOYEE_ID,
    ) -> User:
        user = User()
        user.id = user_id
        user.tenant_id = tenant_id
        user.email = "manager@acme.com"
        user.full_name = "Test Manager"
        user.hashed_password = hashed_password
        user.role = role
        user.is_active = True
        user.employee_id = employee_id
        return user
    return _make


@pytest.fixture
def tm_user(make_user) -> User:
    return make_user(role="tm")


@pytest.fixture
def dev_user(make_user) -> User:
    return make_user(role="dev", user_id=uuid.uuid4())


@pytest.fixture
def admin_user(make_user) -> User:
    return make_user(role="admin", user_id=uuid.uuid4())


@pytest.fixture
def make_skill():
    def _make(label: str = "Python", esco_uri: str | None = None) -> Skill:
        skill = Skill()
        skill.id = SKILL_ID
        skill.preferred_label = label
        skill.esco_uri = esco_uri or f"http://data.europa.eu/esco/skill/{label.lower()}"
        skill.alt_labels = [label.lower()]
        return skill
    return _make


@pytest.fixture
def make_employee_skill(make_skill):
    def _make(
        label: str = "Python",
        nivel: str = "senior",
        source: str = "github",
        confidence: float = 0.9,
    ) -> EmployeeSkill:
        es = EmployeeSkill()
        es.id = uuid.uuid4()
        es.tenant_id = TENANT_ID
        es.employee_id = EMPLOYEE_ID
        es.skill_id = SKILL_ID
        es.skill = make_skill(label)
        es.nivel = nivel
        es.confidence_score = confidence
        es.source = source
        es.evidence = {}
        return es
    return _make


@pytest.fixture
def make_employee(make_employee_skill):
    def _make(
        skills: list[str] | None = None,
        department: str = "Engineering",
    ) -> Employee:
        emp = Employee()
        emp.id = EMPLOYEE_ID
        emp.tenant_id = TENANT_ID
        emp.email = "dev@acme.com"
        emp.full_name = "Juan Pérez"
        emp.title = "Senior Developer"
        emp.department = department
        emp.is_active = True
        emp.external_ids = {"github": "juanperez"}
        emp.skills = [make_employee_skill(label=s) for s in (skills or ["Python", "FastAPI"])]
        return emp
    return _make


@pytest.fixture
def make_project():
    def _make(
        required_skills: list[dict] | None = None,
    ) -> Project:
        p = Project()
        p.id = PROJECT_ID
        p.tenant_id = TENANT_ID
        p.name = "Backend Rewrite"
        p.description = "Migrate monolith to microservices"
        p.status = "planning"
        p.required_skills = required_skills or [
            {"skill_label": "Python", "esco_uri": None, "level": "senior", "weight": 1.0},
            {"skill_label": "FastAPI", "esco_uri": None, "level": "mid", "weight": 0.8},
        ]
        p.created_by = USER_ID
        return p
    return _make


# ── Mock DB session ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    db.get = AsyncMock()
    db.flush = AsyncMock()
    return db
