"""
Integration test conftest.
Uses the real PostgreSQL database. Truncates all tables before each test.

Uses NullPool on all test engines so connections are never pooled across
event loops (pytest-asyncio creates a new loop per test function).
"""

import psycopg2
import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from etip_api.database import get_db
from etip_api.main import app

_DATABASE_URL = "postgresql+asyncpg://etip:etip@localhost:5432/etip"
_DATABASE_DSN = "postgresql://etip:etip@localhost:5432/etip"

_KILL_ALL = """
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = 'etip'
      AND pid <> pg_backend_pid()
"""

_TRUNCATE_SQL = """
    TRUNCATE
        refresh_tokens, recommendations, employee_skills,
        allocations, time_off, connector_configs, audit_log,
        projects, employees, users, tenants
    RESTART IDENTITY CASCADE
"""


@pytest.fixture(autouse=True)
def clean_db():
    """
    Kill ALL other connections to the test DB then truncate all tables.
    Uses sync psycopg2 — no event loop, no risk of zombie transactions.
    """
    conn = psycopg2.connect(_DATABASE_DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(_KILL_ALL)
    cur.execute("SET lock_timeout = '5s'")
    cur.execute(_TRUNCATE_SQL)
    cur.close()
    conn.close()
    yield


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """Raw async DB session for seeding test data — bypasses app RLS layer."""
    engine = create_async_engine(_DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    session = factory()
    try:
        yield session
    finally:
        # Suppress asyncpg ROLLBACK errors during event loop teardown on Windows
        try:
            await session.close()
        except Exception:
            pass
        try:
            await engine.dispose()
        except Exception:
            pass


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """
    Real HTTP client against the FastAPI app.
    Overrides get_db with a NullPool engine so SQLAlchemy never reuses
    connections across event loops.
    """
    engine = create_async_engine(_DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db(request: Request):
        tenant_id = getattr(request.state, "tenant_id", None)
        async with factory() as session:
            if tenant_id:
                await session.execute(text(f"SET LOCAL rls.tenant_id = '{tenant_id}'"))
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


# ── Shared helpers ─────────────────────────────────────────────────────────────

async def register(
    client: AsyncClient,
    *,
    slug: str = "acme",
    email: str = "admin@acme.com",
    password: str = "Password1!",
    company_name: str = "ACME Corp",
) -> tuple[str, str]:
    """Register a new company. Returns (access_token, tenant_id)."""
    resp = await client.post(
        "/auth/register",
        json={"company_name": company_name, "slug": slug, "email": email, "password": password},
    )
    assert resp.status_code == 201, f"register failed: {resp.text}"
    token = resp.json()["access_token"]
    me = await client.get("/auth/me", headers=auth(token))
    assert me.status_code == 200, f"me failed: {me.text}"
    tenant_id = me.json()["tenant_id"]
    return token, tenant_id


async def login(client: AsyncClient, email: str, password: str, tenant_id: str) -> str:
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": password, "tenant_id": tenant_id},
    )
    assert resp.status_code == 200, f"login failed: {resp.text}"
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
