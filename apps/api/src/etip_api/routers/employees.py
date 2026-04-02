import csv
import io
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from etip_api.auth.dependencies import get_current_user, require_role
from etip_api.database import get_db
from etip_api.models.allocation import Allocation, TimeOff
from etip_api.models.employee import Employee
from etip_api.models.skill import EmployeeSkill, Skill
from etip_api.models.user import User
from etip_api.services.audit import log_action

router = APIRouter(prefix="/employees", tags=["employees"])


# ── Response schemas ──────────────────────────────────────────────────────────

class SkillOut(BaseModel):
    id: UUID
    skill_label: str
    esco_uri: str | None
    level: str | None
    confidence_score: float
    source: str


class EmployeeOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    title: str | None
    department: str | None
    is_active: bool
    skills: list[SkillOut] = []


class AvailabilityOut(BaseModel):
    employee_id: UUID
    capacity_pct: float
    allocated_pct: float
    availability_pct: float


class EmployeeListOut(BaseModel):
    items: list[EmployeeOut]
    total: int
    page: int
    page_size: int


class ImportSummaryOut(BaseModel):
    created: int
    updated: int
    errors: list[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _get_employee_or_404(employee_id: UUID, tenant_id: UUID, db: AsyncSession) -> Employee:
    emp = await db.get(Employee, employee_id, options=[selectinload(Employee.skills).selectinload(EmployeeSkill.skill)])
    if not emp or not emp.is_active or emp.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return emp


def _to_skill_out(es: EmployeeSkill) -> SkillOut:
    return SkillOut(
        id=es.skill_id,
        skill_label=es.skill.preferred_label,
        esco_uri=es.skill.esco_uri,
        level=es.nivel,
        confidence_score=es.confidence_score,
        source=es.source,
    )


def _to_employee_out(emp: Employee) -> EmployeeOut:
    return EmployeeOut(
        id=emp.id,
        email=emp.email,
        full_name=emp.full_name,
        title=emp.title,
        department=emp.department,
        is_active=emp.is_active,
        skills=[_to_skill_out(es) for es in emp.skills],
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=EmployeeListOut)
async def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("tm", "admin")),
) -> EmployeeListOut:
    q = (
        select(Employee)
        .where(Employee.tenant_id == current_user.tenant_id, Employee.is_active.is_(True))
        .options(selectinload(Employee.skills).selectinload(EmployeeSkill.skill))
    )
    if department:
        q = q.where(Employee.department == department)
    if search:
        safe = _escape_like(search)
        q = q.where(
            Employee.full_name.ilike(f"%{safe}%", escape="\\") |
            Employee.email.ilike(f"%{safe}%", escape="\\")
        )

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    employees = result.scalars().all()

    return EmployeeListOut(
        items=[_to_employee_out(e) for e in employees],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/import/csv", response_model=ImportSummaryOut)
async def import_employees_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> ImportSummaryOut:
    """
    Import employees from a UTF-8 CSV file. Admin-only.
    Required columns: email, full_name
    Optional columns: title, department
    Existing employees (matched by email within the tenant) are updated; new ones are created.
    """
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None or not {"email", "full_name"}.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV must contain columns: email, full_name",
        )

    created = 0
    updated = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):
        email = (row.get("email") or "").strip().lower()
        full_name = (row.get("full_name") or "").strip()

        if not email or not full_name:
            errors.append(f"Row {row_num}: 'email' and 'full_name' are required")
            continue

        title = (row.get("title") or "").strip() or None
        department = (row.get("department") or "").strip() or None

        result = await db.execute(
            select(Employee).where(
                Employee.tenant_id == current_user.tenant_id,
                Employee.email == email,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.full_name = full_name
            existing.title = title
            existing.department = department
            updated += 1
        else:
            db.add(Employee(
                tenant_id=current_user.tenant_id,
                email=email,
                full_name=full_name,
                title=title,
                department=department,
            ))
            created += 1

    await db.commit()
    await log_action(
        db,
        actor=current_user,
        action="employees.csv_import",
        resource_type="employee",
        payload={"created": created, "updated": updated, "error_count": len(errors)},
    )

    return ImportSummaryOut(created=created, updated=updated, errors=errors)


@router.get("/me", response_model=EmployeeOut)
async def my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmployeeOut:
    if not current_user.employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No employee profile linked to this user")
    emp = await _get_employee_or_404(current_user.employee_id, current_user.tenant_id, db)
    return _to_employee_out(emp)


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("tm", "admin")),
) -> EmployeeOut:
    emp = await _get_employee_or_404(employee_id, current_user.tenant_id, db)
    return _to_employee_out(emp)


@router.get("/{employee_id}/availability", response_model=AvailabilityOut)
async def get_availability(
    employee_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("tm", "admin")),
) -> AvailabilityOut:
    await _get_employee_or_404(employee_id, current_user.tenant_id, db)

    # Sum allocations overlapping the requested date range, scoped to tenant
    alloc_result = await db.execute(
        select(func.coalesce(func.avg(Allocation.allocation_pct), 0.0)).where(
            Allocation.tenant_id == current_user.tenant_id,
            Allocation.employee_id == employee_id,
            Allocation.start_date <= end_date,
            Allocation.end_date >= start_date,
        )
    )
    allocated_pct: float = float(alloc_result.scalar_one())

    return AvailabilityOut(
        employee_id=employee_id,
        capacity_pct=100.0,
        allocated_pct=round(allocated_pct, 1),
        availability_pct=round(max(0.0, 100.0 - allocated_pct), 1),
    )
