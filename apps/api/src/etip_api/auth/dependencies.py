from collections.abc import Callable
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from etip_api.auth.jwt import decode_access_token
from etip_api.database import get_db, get_db_public
from etip_api.models.user import User

bearer_scheme = HTTPBearer()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_public),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise unauthorized

    user = await db.get(User, UUID(payload["sub"]))
    if not user or not user.is_active:
        raise unauthorized

    # For platform admins who switched to a different tenant, the JWT carries the active
    # tenant_id (set by TenantMiddleware → request.state.tenant_id). Override user.tenant_id
    # so every route handler that filters by current_user.tenant_id uses the correct tenant.
    active_tenant_id: str | None = getattr(request.state, "tenant_id", None)
    if active_tenant_id and str(user.tenant_id) != active_tenant_id:
        user.tenant_id = UUID(active_tenant_id)

    return user


def require_role(*roles: str) -> Callable:
    """
    Dependency factory for RBAC.

    Usage:
        @router.post("/projects")
        async def create(user: User = Depends(require_role("tm", "admin"))): ...
    """
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not allowed. Required: {list(roles)}",
            )
        return current_user

    return _check
