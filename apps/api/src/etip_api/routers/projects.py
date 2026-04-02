from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from etip_api.auth.dependencies import get_current_user, require_role
from etip_api.database import get_db
from etip_api.models.project import Project
from etip_api.models.user import User
from etip_api.services.audit import log_action

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RequiredSkill(BaseModel):
    skill_label: str
    esco_uri: str | None = None
    level: str | None = None     # junior | mid | senior | expert
    weight: float = 1.0          # importance multiplier for scoring


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    required_skills: list[RequiredSkill] = []

    @model_validator(mode="after")
    def check_dates(self) -> "ProjectCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    required_skills: list[RequiredSkill] | None = None

    @model_validator(mode="after")
    def check_dates(self) -> "ProjectUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    start_date: date | None
    end_date: date | None
    status: str
    required_skills: list[RequiredSkill]
    created_by: UUID | None


class ProjectListOut(BaseModel):
    items: list[ProjectOut]
    total: int
    page: int
    page_size: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_skill(s: dict) -> RequiredSkill:
    """Handle both old (label/nivel) and new (skill_label/level) JSONB keys."""
    return RequiredSkill(
        skill_label=s.get("skill_label", s.get("label", "")),
        esco_uri=s.get("esco_uri"),
        level=s.get("level", s.get("nivel")),
        weight=s.get("weight", 1.0),
    )


def _to_out(p: Project) -> ProjectOut:
    return ProjectOut(
        id=p.id,
        name=p.name,
        description=p.description,
        start_date=p.start_date,
        end_date=p.end_date,
        status=p.status,
        required_skills=[_normalize_skill(s) for s in (p.required_skills or [])],
        created_by=p.created_by,
    )


async def _get_or_404(project_id: UUID, tenant_id: UUID, db: AsyncSession) -> Project:
    p = await db.get(Project, project_id)
    if not p or p.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return p


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=ProjectListOut)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("tm", "admin")),
) -> ProjectListOut:
    q = select(Project).where(Project.tenant_id == current_user.tenant_id)
    if project_status:
        q = q.where(Project.status == project_status)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    return ProjectListOut(items=[_to_out(p) for p in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("tm", "admin")),
) -> ProjectOut:
    project = Project(
        tenant_id=current_user.tenant_id,
        name=body.name,
        description=body.description,
        start_date=body.start_date,
        end_date=body.end_date,
        required_skills=[s.model_dump() for s in body.required_skills],
        created_by=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    await log_action(db, current_user, "project.created", "project", project.id, {"name": project.name})
    return _to_out(project)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("tm", "admin")),
) -> ProjectOut:
    return _to_out(await _get_or_404(project_id, current_user.tenant_id, db))


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("tm", "admin")),
) -> ProjectOut:
    project = await _get_or_404(project_id, current_user.tenant_id, db)

    for field, value in body.model_dump(exclude_none=True).items():
        if field == "required_skills":
            value = [s if isinstance(s, dict) else s.model_dump() for s in value]
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    await log_action(db, current_user, "project.updated", "project", project.id)
    return _to_out(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> None:
    project = await _get_or_404(project_id, current_user.tenant_id, db)
    await db.delete(project)
    await db.commit()
    await log_action(db, current_user, "project.deleted", "project", project_id)
