from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from etip_api.models.audit import AuditLog
from etip_api.models.user import User


async def log_action(
    db: AsyncSession,
    actor: User,
    action: str,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    payload: dict | None = None,
    ip_address: str | None = None,
) -> None:
    entry = AuditLog(
        tenant_id=actor.tenant_id,
        actor_id=actor.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.commit()
