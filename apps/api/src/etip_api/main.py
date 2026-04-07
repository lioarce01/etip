from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from etip_api.limiter import limiter
from etip_api.middleware import TenantMiddleware
from etip_api.routers import analytics, auth, connectors, employees, projects, recommendations, tenants, users
from etip_core.plugin_manager import load_connectors
from etip_core.settings import get_settings

settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Discover and register all installed connector plugins
    load_connectors()
    yield


app = FastAPI(
    title="ETIP API",
    description="Engineering Talent Intelligence Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router)                              # /auth/...
app.include_router(tenants.router)                           # /tenants/...
app.include_router(analytics.router, prefix=API_PREFIX)     # /api/v1/analytics
app.include_router(employees.router, prefix=API_PREFIX)     # /api/v1/employees
app.include_router(projects.router, prefix=API_PREFIX)      # /api/v1/projects
app.include_router(recommendations.router, prefix=API_PREFIX)  # /api/v1/projects/{id}/recommendations
app.include_router(connectors.router, prefix=API_PREFIX)    # /api/v1/connectors
app.include_router(users.router, prefix=API_PREFIX)         # /api/v1/users


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
