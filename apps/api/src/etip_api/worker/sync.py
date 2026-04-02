"""
Synchronous sync runner called from Celery tasks.
Orchestrates: employees → identity merge → skills → ESCO normalization → DB upsert.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from etip_core.plugin_manager import pm
from etip_core.schemas import EmployeeDTO, ProjectDTO, SkillDTO

logger = logging.getLogger(__name__)


def run_sync(tenant_id: str, connector_name: str, config: dict, connector_id: str | None = None) -> dict:
    from etip_api.database import engine
    from sqlalchemy import create_engine
    from etip_core.settings import get_settings
    from sqlalchemy.orm import sessionmaker

    settings = get_settings()
    sync_engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(bind=sync_engine)

    started_at = datetime.now(UTC)
    employees_synced = 0
    skills_synced = 0
    projects_synced = 0
    errors: list[str] = []

    with SessionLocal() as db:
        # Use SET (not SET LOCAL) so the RLS context survives intermediate commits
        db.execute(
            __import__("sqlalchemy").text(f"SET rls.tenant_id = '{tenant_id}'")
        )

        # ── Sync employees ────────────────────────────────────────────────────
        try:
            raw_employees: list[list[dict]] = pm.hook.sync_employees(
                tenant_id=tenant_id, config=config
            )
            for batch in raw_employees:
                for raw in batch:
                    emp_dto = EmployeeDTO(**raw)
                    _upsert_employee(db, tenant_id, emp_dto)
                    employees_synced += 1
            db.commit()
        except Exception as e:
            errors.append(f"employees: {e}")
            logger.exception("Employee sync error")

        # ── Sync skills per employee ──────────────────────────────────────────
        from etip_api.models.employee import Employee
        from etip_api.services.esco import normalize_skill

        employees = db.execute(
            select(Employee).where(
                Employee.tenant_id == uuid.UUID(tenant_id),
                Employee.is_active.is_(True),
            )
        ).scalars().all()

        employees_to_index: list = []

        for emp in employees:
            external_id = emp.external_ids.get(connector_name, emp.email)
            try:
                raw_skills: list[list[dict]] = pm.hook.sync_skills(
                    tenant_id=tenant_id,
                    employee_external_id=external_id,
                    config=config,
                )
                for batch in raw_skills:
                    for raw in batch:
                        skill_dto = SkillDTO(**raw)
                        _upsert_skill(db, tenant_id, emp.id, skill_dto)
                        skills_synced += 1
                db.commit()
                employees_to_index.append(emp.id)
            except Exception as e:
                db.rollback()
                errors.append(f"skills for {emp.id}: {e}")
                logger.exception("Skill sync error for employee_id=%s", emp.id)

        # ── Index employees in Qdrant ─────────────────────────────────────────
        if employees_to_index:
            _index_employees_in_qdrant(db, employees_to_index)

        # ── Sync projects ─────────────────────────────────────────────────────
        try:
            raw_projects: list[list[dict]] = pm.hook.sync_projects(
                tenant_id=tenant_id, config=config
            )
            for batch in raw_projects:
                for raw in batch:
                    proj_dto = ProjectDTO(**raw)
                    _upsert_project(db, tenant_id, proj_dto)
                    projects_synced += 1
            db.commit()
        except Exception as e:
            errors.append(f"projects: {e}")
            logger.exception("Project sync error")

        # ── Update connector sync status ──────────────────────────────────────
        if connector_id:
            from etip_api.models.connector import ConnectorConfig
            final_status = "error" if errors else "idle"
            db.execute(
                update(ConnectorConfig)
                .where(
                    ConnectorConfig.id == uuid.UUID(connector_id),
                    ConnectorConfig.tenant_id == uuid.UUID(tenant_id),
                )
                .values(sync_status=final_status, last_sync_at=datetime.now(UTC))
            )
            db.commit()

    return {
        "connector": connector_name,
        "tenant_id": tenant_id,
        "employees_synced": employees_synced,
        "skills_synced": skills_synced,
        "projects_synced": projects_synced,
        "errors": errors,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
    }


def _normalize_email(email: str) -> str:
    """
    Return a canonical email address for identity deduplication.
    - Lowercases and strips whitespace
    - Strips + alias suffixes (e.g. user+alias@example.com → user@example.com)
    - Removes dots from the local part for Gmail/Googlemail (Gmail ignores them)
    """
    local, _, domain = email.lower().strip().partition("@")
    local = local.split("+")[0]
    if domain in ("gmail.com", "googlemail.com"):
        local = local.replace(".", "")
    return f"{local}@{domain}"


def _upsert_employee(db: Session, tenant_id: str, dto: EmployeeDTO) -> None:
    from etip_api.models.employee import Employee

    email = _normalize_email(dto.email)

    existing = db.execute(
        select(Employee).where(
            Employee.tenant_id == uuid.UUID(tenant_id),
            Employee.email == email,
        )
    ).scalar_one_or_none()

    if existing:
        existing.full_name = dto.full_name
        existing.title = dto.title or existing.title
        existing.department = dto.department or existing.department
        existing.external_ids = {**existing.external_ids, dto.source: dto.external_id}
    else:
        db.add(Employee(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(tenant_id),
            email=email,
            full_name=dto.full_name,
            title=dto.title,
            department=dto.department,
            external_ids={dto.source: dto.external_id},
        ))


def _index_employees_in_qdrant(db: Session, employee_ids: list[uuid.UUID]) -> None:
    """Load employees with their skills and batch-index them into Qdrant."""
    import asyncio
    from etip_api.models.employee import Employee
    from etip_api.models.skill import EmployeeSkill as ES
    from etip_api.services.matching import index_employee_in_qdrant
    from sqlalchemy.orm import selectinload

    refreshed = db.execute(
        select(Employee)
        .where(Employee.id.in_(employee_ids))
        .options(selectinload(Employee.skills).selectinload(ES.skill))
    ).scalars().all()

    async def _run_all():
        await asyncio.gather(*[index_employee_in_qdrant(e) for e in refreshed])

    asyncio.run(_run_all())
    logger.info("Indexed %d employees in Qdrant", len(refreshed))


def _upsert_project(db: Session, tenant_id: str, dto: ProjectDTO) -> None:
    """
    Upsert a project synced from an external connector (e.g. Jira).
    Matches by (tenant_id, name). If the project already exists it updates
    description and required_skills but does not overwrite status.
    required_skills are stored in dto.raw["required_skills"] by the connector.
    """
    from etip_api.models.project import Project

    required_skills = dto.raw.get("required_skills", [])

    existing = db.execute(
        select(Project).where(
            Project.tenant_id == uuid.UUID(tenant_id),
            Project.name == dto.name,
        )
    ).scalar_one_or_none()

    if existing:
        existing.description = dto.description or existing.description
        if required_skills:
            existing.required_skills = required_skills
    else:
        db.add(Project(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(tenant_id),
            name=dto.name,
            description=dto.description,
            status="active",
            required_skills=required_skills,
        ))


def _upsert_skill(db: Session, tenant_id: str, employee_id: uuid.UUID, dto: SkillDTO) -> None:
    from etip_api.models.skill import EmployeeSkill, Skill
    from etip_api.services.esco import normalize_skill

    # Normalize to ESCO
    esco = normalize_skill(dto.raw_label)
    label = esco.get("preferred_label", dto.raw_label) if esco else dto.raw_label
    esco_uri = esco.get("uri") if esco else dto.esco_uri

    # Get or create global skill
    skill = db.execute(
        select(Skill).where(Skill.preferred_label == label)
    ).scalar_one_or_none()

    if not skill:
        skill = Skill(id=uuid.uuid4(), preferred_label=label, esco_uri=esco_uri)
        db.add(skill)
        db.flush()

    # Upsert employee_skill
    emp_skill = db.execute(
        select(EmployeeSkill).where(
            EmployeeSkill.employee_id == employee_id,
            EmployeeSkill.skill_id == skill.id,
            EmployeeSkill.source == dto.source,
        )
    ).scalar_one_or_none()

    if emp_skill:
        emp_skill.confidence_score = dto.confidence_score
        emp_skill.nivel = dto.nivel or emp_skill.nivel
        emp_skill.last_seen_at = datetime.now(UTC)
    else:
        db.add(EmployeeSkill(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(tenant_id),
            employee_id=employee_id,
            skill_id=skill.id,
            nivel=dto.nivel,
            confidence_score=dto.confidence_score,
            source=dto.source,
            evidence=dto.evidence,
            last_seen_at=datetime.now(UTC),
        ))
