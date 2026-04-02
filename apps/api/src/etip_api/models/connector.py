import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from etip_api.database import Base


class ConnectorConfig(Base):
    __tablename__ = "connector_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    connector_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "github"
    config_encrypted: Mapped[dict] = mapped_column(JSONB, default=dict)       # encrypted secrets
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[str | None] = mapped_column(String(50))               # idle | syncing | error | success
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
