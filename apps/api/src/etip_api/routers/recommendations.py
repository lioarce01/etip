from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from etip_api.auth.dependencies import get_current_user, require_role
from etip_api.database import get_db
from etip_api.models.project import Project
from etip_api.models.recommendation import Recommendation
from etip_api.models.user import User
from etip_api.schemas.recommendations import RecommendationOut, SkillMatch
from etip_api.services.audit import log_action
from etip_api.services.matching import run_matching

router = APIRouter(tags=["recommendations"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    feedback: str          # accepted | rejected | maybe
    reason: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/recommendations", response_model=list[RecommendationOut])
async def get_recommendations(
    project_id: UUID,
    top_k: int = Query(10, ge=1, le=50),
    min_available_pct: float = Query(20.0, ge=0.0, le=100.0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("tm", "admin")),
) -> list[RecommendationOut]:
    project = await db.get(Project, project_id)
    if not project or project.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    results = await run_matching(
        db=db,
        project=project,
        top_k=top_k,
        min_available_pct=min_available_pct,
    )

    await log_action(db, current_user, "recommendation.viewed", "project", project_id)
    return results


@router.post(
    "/projects/{project_id}/recommendations/{recommendation_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def submit_feedback(
    project_id: UUID,
    recommendation_id: UUID,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("tm", "admin")),
) -> None:
    if body.feedback not in ("accepted", "rejected", "maybe"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="feedback must be accepted | rejected | maybe")

    rec = await db.get(Recommendation, recommendation_id)
    if not rec or rec.project_id != project_id or rec.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")

    from datetime import UTC, datetime
    rec.feedback = body.feedback
    rec.feedback_reason = body.reason
    rec.feedback_at = datetime.now(UTC)
    await db.commit()

    await log_action(
        db, current_user, "recommendation.feedback", "recommendation", recommendation_id,
        {"feedback": body.feedback, "project_id": str(project_id)},
    )
