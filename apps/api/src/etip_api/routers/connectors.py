from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from etip_api.auth.dependencies import require_role
from etip_api.database import get_db
from etip_api.models.connector import ConnectorConfig
from etip_api.models.user import User
from etip_api.services.audit import log_action
from etip_api.services.crypto import decrypt_config, encrypt_config
from etip_api.worker.tasks import sync_connector_task
from etip_core.plugin_manager import get_connector_names

router = APIRouter(prefix="/connectors", tags=["connectors"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConnectorOut(BaseModel):
    id: UUID
    connector_name: str
    is_active: bool
    sync_status: str | None
    last_sync_at: str | None


class ConnectorConfigCreate(BaseModel):
    connector_name: str
    config: dict        # raw config — encrypted before storage


class SyncTriggerOut(BaseModel):
    task_id: str
    connector_name: str
    status: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ConnectorOut])
async def list_connectors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> list[ConnectorOut]:
    result = await db.execute(
        select(ConnectorConfig).where(ConnectorConfig.tenant_id == current_user.tenant_id)
    )
    configs = result.scalars().all()
    return [
        ConnectorOut(
            id=c.id,
            connector_name=c.connector_name,
            is_active=c.is_active,
            sync_status=c.sync_status,
            last_sync_at=c.last_sync_at.isoformat() if c.last_sync_at else None,
        )
        for c in configs
    ]


@router.get("/available")
async def list_available_connectors(
    _user: User = Depends(require_role("admin")),
) -> list[str]:
    """Returns the slugs of all installed connector plugins."""
    return get_connector_names()


@router.post("", response_model=ConnectorOut, status_code=status.HTTP_201_CREATED)
async def create_connector(
    body: ConnectorConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> ConnectorOut:
    installed = get_connector_names()
    if body.connector_name not in installed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connector '{body.connector_name}' is not installed. Available: {installed}",
        )

    config = ConnectorConfig(
        tenant_id=current_user.tenant_id,
        connector_name=body.connector_name,
        config_encrypted=encrypt_config(body.config),
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)

    await log_action(db, current_user, "connector.configured", "connector", config.id, {"name": body.connector_name})

    return ConnectorOut(
        id=config.id,
        connector_name=config.connector_name,
        is_active=config.is_active,
        sync_status=config.sync_status,
        last_sync_at=None,
    )


@router.post("/{connector_id}/sync", response_model=SyncTriggerOut)
async def trigger_sync(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> SyncTriggerOut:
    config = await db.get(ConnectorConfig, connector_id)
    if not config or config.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    # Dispatch Celery task
    task = sync_connector_task.delay(
        tenant_id=str(current_user.tenant_id),
        connector_name=config.connector_name,
        connector_config=decrypt_config(config.config_encrypted),
        connector_id=str(connector_id),
    )

    config.sync_status = "syncing"
    await db.commit()

    await log_action(db, current_user, "employee.sync_triggered", "connector", connector_id)

    return SyncTriggerOut(task_id=task.id, connector_name=config.connector_name, status="syncing")
