from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from etip_core.settings import get_settings

settings = get_settings()


def create_access_token(user_id: UUID, email: str, role: str, tenant_id: UUID) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "tenant_id": str(tenant_id),
        "type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate an access token.
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def create_pre_auth_token(email: str) -> str:
    """Create a short-lived pre-auth token for multi-tenant tenant selection."""
    payload = {
        "sub": email,
        "type": "pre_auth",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_pre_auth_token(token: str | None) -> dict:
    """
    Decode and validate a pre-auth token.
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    if not token:
        raise jwt.InvalidTokenError("No pre-auth token")
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "pre_auth":
        raise jwt.InvalidTokenError("Not a pre-auth token")
    return payload
