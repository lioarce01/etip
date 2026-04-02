"""
Shared Pydantic DTOs used across the monorepo.
These are the canonical data shapes that flow between connectors and the API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# ── Connector output DTOs (raw, before DB persistence) ────────────────────────

class EmployeeDTO(BaseModel):
    """Minimal employee record returned by a connector's sync_employees hook."""

    external_id: str = Field(description="ID in the source system (Okta uid, HRIS id, etc.)")
    email: EmailStr
    full_name: str
    title: str | None = None
    department: str | None = None
    manager_email: EmailStr | None = None
    source: str = Field(description="Connector slug that produced this record, e.g. 'okta'")
    raw: dict[str, Any] = Field(default_factory=dict, description="Original payload for audit")


class SkillDTO(BaseModel):
    """Skill signal returned by a connector's sync_skills hook."""

    raw_label: str = Field(description="Skill name as returned by the source, e.g. 'python3'")
    esco_uri: str | None = None
    esco_label: str | None = None
    nivel: str | None = Field(
        default=None,
        description="Inferred seniority: junior | mid | senior | expert",
    )
    years_experience: float | None = None
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = Field(description="Connector slug, e.g. 'github'")
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Supporting data: repo names, commit count, etc.",
    )


class ProjectDTO(BaseModel):
    """Project record returned by a connector's sync_projects hook."""

    external_id: str
    name: str
    description: str | None = None
    source: str
    raw: dict[str, Any] = Field(default_factory=dict)


class SyncResultDTO(BaseModel):
    """Summary returned after a full connector sync run."""

    connector: str
    tenant_id: str
    employees_synced: int = 0
    skills_synced: int = 0
    projects_synced: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime


# API response schemas live in etip_api.schemas, not here.
# This file only contains connector-facing DTOs (EmployeeDTO, SkillDTO, etc.).
