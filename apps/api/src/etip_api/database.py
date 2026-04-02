from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from etip_core.settings import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    echo=settings.app_env == "development",
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a DB session with the RLS tenant context set.
    tenant_id is written to request.state by TenantMiddleware before the route runs.
    """
    tenant_id: str | None = getattr(request.state, "tenant_id", None)
    async with AsyncSessionLocal() as session:
        if tenant_id:
            await session.execute(
                text(f"SET LOCAL rls.tenant_id = '{tenant_id}'")
            )
        yield session
