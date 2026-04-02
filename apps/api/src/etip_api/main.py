from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from etip_api.middleware import TenantMiddleware
from etip_api.routers import auth, connectors, employees, projects, recommendations, tenants, users
from etip_core.plugin_manager import load_connectors
from etip_core.settings import get_settings

settings = get_settings()


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
app.include_router(employees.router, prefix=API_PREFIX)     # /api/v1/employees
app.include_router(projects.router, prefix=API_PREFIX)      # /api/v1/projects
app.include_router(recommendations.router, prefix=API_PREFIX)  # /api/v1/projects/{id}/recommendations
app.include_router(connectors.router, prefix=API_PREFIX)    # /api/v1/connectors
app.include_router(users.router, prefix=API_PREFIX)         # /api/v1/users


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
