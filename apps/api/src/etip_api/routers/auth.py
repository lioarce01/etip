import hashlib
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from etip_api.auth.dependencies import get_current_user
from etip_api.limiter import limiter
from etip_api.auth.jwt import create_access_token, create_pre_auth_token, decode_pre_auth_token
from etip_api.auth.password import hash_password, verify_password
from etip_api.database import get_db, get_db_public
from etip_api.models.tenant import Tenant
from etip_api.models.user import RefreshToken, User
from etip_core.settings import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


# ── Request / Response schemas ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    company_name: str
    slug: str
    email: EmailStr
    password: str

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("slug must be 3-63 lowercase alphanumeric characters or hyphens, no leading/trailing hyphens")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    pre_auth_token: str | None = None
    tenants: list["TenantLookupResponse"] | None = None


class TenantLookupResponse(BaseModel):
    id: UUID
    name: str
    slug: str


class MeResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    role: str
    tenant_id: str
    is_platform_admin: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SelectTenantRequest(BaseModel):
    tenant_id: UUID


class SwitchTenantRequest(BaseModel):
    tenant_id: UUID


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth",
    )


def _set_pre_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="pre_auth_token",
        value=token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=5 * 60,  # 5 minutes
        path="/auth",
    )


async def _issue_tokens(db: AsyncSession, response: Response, user: User) -> TokenResponse:
    """Create access + refresh tokens and set the cookie."""
    access_token = create_access_token(user.id, user.email, user.role, user.tenant_id)
    raw_refresh = str(uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw_refresh),
        expires_at=expires_at,
    ))
    await db.commit()
    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token)


async def _issue_tokens_login(
    db: AsyncSession,
    response: Response,
    user: User,
    override_tenant_id: UUID | None = None,
) -> LoginResponse:
    """Create access + refresh tokens and set the cookie. Returns LoginResponse."""
    effective_tenant_id = override_tenant_id if override_tenant_id is not None else user.tenant_id
    access_token = create_access_token(user.id, user.email, user.role, effective_tenant_id)
    raw_refresh = str(uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw_refresh),
        expires_at=expires_at,
    ))
    await db.commit()
    _set_refresh_cookie(response, raw_refresh)
    return LoginResponse(access_token=access_token)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Create a new company (Tenant) and its first admin user in one atomic operation.
    Returns an access token so the user is logged in immediately.

    The slug becomes the company's identifier on the login page
    (frontend resolves tenant_id via GET /auth/tenant-by-slug/{slug}).
    """
    # Check slug uniqueness — tenants table has no RLS, so this query is always global
    existing_tenant = (await db.execute(
        select(Tenant).where(Tenant.slug == body.slug)
    )).scalar_one_or_none()
    if existing_tenant:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")

    # Create tenant
    tenant = Tenant(name=body.company_name, slug=body.slug)
    db.add(tenant)
    await db.flush()  # populate tenant.id before inserting the user

    # The users table has RLS. Since this is an unauthenticated request, no RLS context
    # was set by get_db. We activate it now so the INSERT passes the policy check.
    await db.execute(text("SET LOCAL rls.tenant_id = :tid").bindparams(tid=str(tenant.id)))

    # Create first admin user
    user = User(
        tenant_id=tenant.id,
        email=body.email,
        hashed_password=hash_password(body.password),
        role="admin",
    )
    db.add(user)
    await db.flush()

    return await _issue_tokens(db, response, user)


@router.get("/tenant-by-slug/{slug}", response_model=TenantLookupResponse)
async def tenant_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db_public),
) -> TenantLookupResponse:
    """
    Resolve a company slug to its tenant_id.
    Used by the frontend login page: the user types their company slug,
    the frontend fetches the tenant_id, then submits the login form.
    """
    tenant = (await db.execute(
        select(Tenant).where(Tenant.slug == slug)
    )).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return TenantLookupResponse(id=tenant.id, name=tenant.name, slug=tenant.slug)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_public),
) -> LoginResponse:
    """
    Email + password login. Finds all tenants the user belongs to.
    - Single tenant: returns access_token directly
    - Multiple tenants: returns pre_auth_token + tenants list for selection
    """
    # Cross-tenant query — no RLS context needed
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    users = result.scalars().all()

    # Verify password against each user record
    matching = [u for u in users if verify_password(body.password, u.hashed_password)]
    if not matching:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Update last_login_at for all matching users
    for u in matching:
        u.last_login_at = datetime.now(UTC)
    await db.commit()

    if len(matching) == 1:
        # Direct login — issue tokens immediately
        return await _issue_tokens_login(db, response, matching[0])

    # Multiple tenants — issue a pre-auth token, return tenant list
    pre_auth = create_pre_auth_token(body.email)
    tenant_ids = [u.tenant_id for u in matching]
    tenants_result = await db.execute(
        select(Tenant).where(Tenant.id.in_(tenant_ids)).order_by(Tenant.name)
    )
    tenants = tenants_result.scalars().all()

    _set_pre_auth_cookie(response, pre_auth)
    return LoginResponse(
        pre_auth_token=pre_auth,
        tenants=[TenantLookupResponse(id=t.id, name=t.name, slug=t.slug) for t in tenants],
    )


@router.post("/select-tenant", response_model=LoginResponse)
@limiter.limit("10/minute")
async def select_tenant(
    request: Request,
    body: SelectTenantRequest,
    response: Response,
    pre_auth_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db_public),
) -> LoginResponse:
    """
    Complete multi-tenant login by selecting a specific tenant.
    Requires a valid pre_auth_token cookie from the login endpoint.
    """
    try:
        payload = decode_pre_auth_token(pre_auth_token)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired pre-auth token")

    email = payload.get("sub")
    user = await db.scalar(
        select(User).where(
            User.email == email,
            User.tenant_id == body.tenant_id,
            User.is_active.is_(True),
        )
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this tenant")

    response.delete_cookie("pre_auth_token", path="/auth")
    return await _issue_tokens_login(db, response, user)


@router.get("/tenants", response_model=list[TenantLookupResponse])
async def list_my_tenants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> list[TenantLookupResponse]:
    """
    Get all tenants the current user belongs to.
    Platform admins see all tenants; regular users see only their own.
    """
    if current_user.is_platform_admin:
        tenants_result = await db.execute(select(Tenant).order_by(Tenant.name))
    else:
        # Find all tenants this email belongs to
        user_rows = await db.execute(
            select(User.tenant_id).where(
                User.email == current_user.email,
                User.is_active.is_(True),
            )
        )
        tenant_ids = [r[0] for r in user_rows.all()]
        tenants_result = await db.execute(
            select(Tenant).where(Tenant.id.in_(tenant_ids)).order_by(Tenant.name)
        )

    tenants = tenants_result.scalars().all()
    return [TenantLookupResponse(id=t.id, name=t.name, slug=t.slug) for t in tenants]


@router.post("/switch-tenant", response_model=LoginResponse)
async def switch_tenant(
    body: SwitchTenantRequest,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_public),
) -> LoginResponse:
    """
    Switch to a different tenant. Requires authentication.
    Regular users can only switch to tenants they belong to.
    Platform admins can switch to any tenant.
    """
    # Verify access
    if current_user.is_platform_admin:
        # Platform admin: find real user in target tenant, or use current user as fallback
        target_user = await db.scalar(
            select(User).where(
                User.email == current_user.email,
                User.tenant_id == body.tenant_id,
                User.is_active.is_(True),
            )
        )
        if not target_user:
            # Platform admin without explicit user in that tenant — allow access
            # Create JWT with target tenant but current user ID (not ideal but functional)
            target_user = current_user
    else:
        target_user = await db.scalar(
            select(User).where(
                User.email == current_user.email,
                User.tenant_id == body.tenant_id,
                User.is_active.is_(True),
            )
        )
        if not target_user:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this tenant")

    # Revoke current refresh token
    if refresh_token:
        token_hash = _hash_token(refresh_token)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(revoked=True)
        )

    response.delete_cookie("refresh_token", path="/auth")

    return await _issue_tokens_login(db, response, target_user, override_tenant_id=body.tenant_id)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_hash = _hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > datetime.now(UTC),
        )
    )
    db_token: RefreshToken | None = result.scalar_one_or_none()

    if not db_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = await db.get(User, db_token.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Rotate: revoke old token, issue new
    db_token.revoked = True
    raw_new = str(uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshToken(user_id=user.id, token_hash=_hash_token(raw_new), expires_at=expires_at))
    await db.commit()

    _set_refresh_cookie(response, raw_new)
    return TokenResponse(access_token=create_access_token(user.id, user.email, user.role, user.tenant_id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> None:
    if refresh_token:
        token_hash = _hash_token(refresh_token)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(revoked=True)
        )
        await db.commit()
    response.delete_cookie("refresh_token", path="/auth")


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=str(current_user.tenant_id),
        is_platform_admin=current_user.is_platform_admin,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(hashed_password=hash_password(body.new_password))
    )
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id)
        .values(revoked=True)
    )
    await db.commit()
