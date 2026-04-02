"""Recommendation response schemas — shared between router and matching service."""

from uuid import UUID
from pydantic import BaseModel


class SkillMatch(BaseModel):
    skill_label: str
    esco_uri: str | None
    required_level: str | None
    matched: bool


class EmployeeInRec(BaseModel):
    id: UUID
    email: str
    full_name: str
    title: str | None
    department: str | None
    is_active: bool


class RecommendationOut(BaseModel):
    id: UUID
    employee: EmployeeInRec
    score: float
    skill_matches: list[SkillMatch]
    availability_pct: float
    explanation: str | None
    feedback: str | None
