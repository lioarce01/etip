from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from etip_api.auth.dependencies import require_role
from etip_api.database import get_db
from etip_api.models.employee import Employee
from etip_api.models.project import Project
from etip_api.models.recommendation import Recommendation
from etip_api.models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AnalyticsOut(BaseModel):
    total_employees: int
    total_projects: int
    total_recommendations: int
    accepted_count: int
    rejected_count: int
    maybe_count: int
    no_feedback_count: int
    precision_at_5: float
    precision_at_10: float
    acceptance_rate: float


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=AnalyticsOut)
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("tm", "admin")),
) -> AnalyticsOut:
    """Return analytics KPIs for the tenant."""
    tid = current_user.tenant_id

    # Total active employees
    total_employees_result = await db.execute(
        select(func.count()).select_from(
            select(Employee).where(Employee.tenant_id == tid, Employee.is_active.is_(True)).subquery()
        )
    )
    total_employees = total_employees_result.scalar_one()

    # Total projects
    total_projects_result = await db.execute(
        select(func.count()).select_from(
            select(Project).where(Project.tenant_id == tid).subquery()
        )
    )
    total_projects = total_projects_result.scalar_one()

    # Feedback counts
    rows = (await db.execute(
        select(Recommendation.feedback, func.count())
        .where(Recommendation.tenant_id == tid)
        .group_by(Recommendation.feedback)
    )).all()

    counts = {r[0]: r[1] for r in rows}
    accepted = counts.get("accepted", 0)
    rejected = counts.get("rejected", 0)
    maybe = counts.get("maybe", 0)
    no_feedback = counts.get(None, 0)
    total_recs = accepted + rejected + maybe + no_feedback

    # Acceptance rate
    feedback_total = accepted + rejected + maybe
    acceptance_rate = round(accepted / feedback_total, 4) if feedback_total else 0.0

    # Precision@K helper: per project, take top-K by score DESC, skip if <k rows
    async def precision_at_k(k: int) -> float:
        project_ids_result = await db.execute(
            select(Project.id).where(Project.tenant_id == tid)
        )
        project_ids = [r[0] for r in project_ids_result.all()]
        if not project_ids:
            return 0.0

        accepted_in_topk = 0
        total_in_topk = 0

        for pid in project_ids:
            top_recs = (await db.execute(
                select(Recommendation.feedback)
                .where(Recommendation.tenant_id == tid, Recommendation.project_id == pid)
                .order_by(Recommendation.score.desc())
                .limit(k)
            )).scalars().all()

            if len(top_recs) < k:
                continue  # skip projects with fewer than k recs
            accepted_in_topk += sum(1 for f in top_recs if f == "accepted")
            total_in_topk += len(top_recs)

        return round(accepted_in_topk / total_in_topk, 4) if total_in_topk else 0.0

    p5 = await precision_at_k(5)
    p10 = await precision_at_k(10)

    return AnalyticsOut(
        total_employees=total_employees,
        total_projects=total_projects,
        total_recommendations=total_recs,
        accepted_count=accepted,
        rejected_count=rejected,
        maybe_count=maybe,
        no_feedback_count=no_feedback,
        precision_at_5=p5,
        precision_at_10=p10,
        acceptance_rate=acceptance_rate,
    )
