import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from etip_api.auth.dependencies import get_current_user, require_role
from etip_api.database import get_db
from etip_api.models.tenant import Tenant
from etip_api.models.user import User

router = APIRouter(prefix="/tenants", tags=["tenants"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


# ── Schemas ───────────────────────────────────────────────────────────────────

class TenantOut(BaseModel):
    id: UUID
    slug: str
    name: str
    plan: str


class TenantUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None and not _SLUG_RE.match(v):
            raise ValueError("slug must be 3-63 lowercase alphanumeric characters or hyphens, no leading/trailing hyphens")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_tenant_or_404(tenant_id: UUID, db: AsyncSession) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def _to_out(t: Tenant) -> TenantOut:
    return TenantOut(id=t.id, slug=t.slug, name=t.name, plan=t.plan)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/me", response_model=TenantOut)
async def get_my_tenant(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TenantOut:
    """Return the tenant (company) the current user belongs to."""
    return _to_out(await _get_tenant_or_404(current_user.tenant_id, db))


@router.patch("/me", response_model=TenantOut)
async def update_my_tenant(
    body: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> TenantOut:
    """Admins can rename the company or change its slug."""
    tenant = await _get_tenant_or_404(current_user.tenant_id, db)

    if body.slug is not None and body.slug != tenant.slug:
        conflict = (await db.execute(
            select(Tenant).where(Tenant.slug == body.slug)
        )).scalar_one_or_none()
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")
        tenant.slug = body.slug

    if body.name is not None:
        tenant.name = body.name

    await db.commit()
    await db.refresh(tenant)
    return _to_out(tenant)
