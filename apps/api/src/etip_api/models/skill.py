import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from etip_api.database import Base


class Skill(Base):
    """Global skill reference table, normalised to ESCO. Not tenant-scoped."""

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    esco_uri: Mapped[str | None] = mapped_column(String(512), unique=True)
    preferred_label: Mapped[str] = mapped_column(String(255), nullable=False)
    alt_labels: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    broader_uri: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee_skills: Mapped[list["EmployeeSkill"]] = relationship(back_populates="skill")


class EmployeeSkill(Base):
    """Skills inferred/extracted for a specific employee (tenant-scoped via employee)."""

    __tablename__ = "employee_skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False)
    nivel: Mapped[str | None] = mapped_column(String(50))          # junior | mid | senior | expert
    years_experience: Mapped[float | None] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    source: Mapped[str] = mapped_column(String(100))               # github | jira | hris | manual
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped["Employee"] = relationship(back_populates="skills")  # type: ignore[name-defined]
    skill: Mapped["Skill"] = relationship(back_populates="employee_skills")
