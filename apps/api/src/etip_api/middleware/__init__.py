"""
TenantMiddleware — extracts tenant_id from the JWT and stores it on
request.state so get_db() can activate the correct RLS context.

This middleware never raises 401 itself; it just sets (or leaves None)
the tenant_id.  Individual route dependencies enforce authentication.
"""

import logging

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from etip_api.auth.jwt import decode_access_token

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        tenant_id: str | None = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]
            try:
                payload = decode_access_token(token)
                tenant_id = payload.get("tenant_id")
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                pass  # route dependency will handle the 401

        request.state.tenant_id = tenant_id
        return await call_next(request)
