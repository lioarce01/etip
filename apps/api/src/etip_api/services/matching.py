"""
Matching engine — pipeline:
  1. Candidate pool: active employees filtered by availability
  2. Vector search via Qdrant (fastembed, local OSS — no API key)
  3. Skill overlap score re-ranks Qdrant results
  4. LLM explanation for top-K results via LiteLLM
  5. Persist Recommendation rows & return

Qdrant is queried with an embedding of the project's required skills.
Employee profile vectors are indexed during connector sync (see sync.py).
Falls back to pure skill-overlap scoring if Qdrant has no vectors yet.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta

logger = logging.getLogger(__name__)

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from etip_api.models.allocation import Allocation
from etip_api.models.employee import Employee
from etip_api.models.project import Project
from etip_api.models.recommendation import Recommendation
from etip_api.models.skill import EmployeeSkill, Skill
from etip_api.schemas.recommendations import RecommendationOut, SkillMatch
from etip_api.services.embedding import embed_project_requirements
from etip_api.services.llm import generate_explanation
from etip_core.settings import get_settings

settings = get_settings()

_flashrank_ranker: object = None


def _get_ranker():
    global _flashrank_ranker
    if _flashrank_ranker is None:
        from flashrank import Ranker
        _flashrank_ranker = Ranker()
    return _flashrank_ranker


async def run_matching(
    db: AsyncSession,
    project: Project,
    top_k: int = 10,
    min_available_pct: float = 20.0,
) -> list[RecommendationOut]:
    required: list[dict] = project.required_skills or []
    if not required:
        return []

    # 1. Vector search via Qdrant to get candidate pool (fast ANN retrieval)
    qdrant_ids = await _qdrant_search(project, top_k=top_k * 5)

    # 2. Load employees — prefer Qdrant hits, fall back to all active employees
    if qdrant_ids:
        emp_result = await db.execute(
            select(Employee)
            .where(Employee.id.in_(qdrant_ids), Employee.is_active.is_(True))
            .options(selectinload(Employee.skills).selectinload(EmployeeSkill.skill))
        )
    else:
        emp_result = await db.execute(
            select(Employee)
            .where(Employee.is_active.is_(True))
            .options(selectinload(Employee.skills).selectinload(EmployeeSkill.skill))
        )
    employees = emp_result.scalars().all()

    # 3. Filter by availability (skip fully allocated employees)
    available_employees = []
    for emp in employees:
        avail_pct = await _get_available_pct(db, emp.id, emp.tenant_id, project.start_date, project.end_date)
        if avail_pct >= min_available_pct:
            available_employees.append((emp, avail_pct))

    if not available_employees:
        return []

    # 4. Score each candidate by skill overlap
    scored: list[tuple[Employee, float, float, list[SkillMatch]]] = []
    for emp, avail_pct in available_employees:
        score, skill_matches = _skill_overlap_score(emp, required)
        scored.append((emp, score, avail_pct, skill_matches))

    # Drop employees with zero skill overlap — no match at all
    scored = [(emp, score, avail, matches) for emp, score, avail, matches in scored if score > 0]

    # Sort by score desc, take top_k * 2 for cross-encoder rerank
    scored.sort(key=lambda x: x[1], reverse=True)
    candidates = scored[: top_k * 2]

    # 5. Cross-encoder rerank (flashrank ms-marco-MiniLM, CPU-only)
    candidates = _rerank_candidates(project, candidates)

    # 6. Generate LLM explanations for top_k
    results: list[RecommendationOut] = []
    for emp, score, avail_pct, skill_matches in candidates[:top_k]:
        explanation = await generate_explanation(project, emp, skill_matches)

        # Upsert: update score/explanation on re-run, preserve existing feedback
        stmt = (
            pg_insert(Recommendation)
            .values(
                id=uuid.uuid4(),
                tenant_id=project.tenant_id,
                project_id=project.id,
                employee_id=emp.id,
                score=round(score, 3),
                explanation=explanation,
            )
            .on_conflict_do_update(
                constraint="uq_recommendation_project_employee",
                set_={"score": round(score, 3), "explanation": explanation},
            )
            .returning(Recommendation.id, Recommendation.feedback)
        )
        row = (await db.execute(stmt)).one()

        from etip_api.schemas.recommendations import EmployeeInRec
        results.append(
            RecommendationOut(
                id=row.id,
                employee=EmployeeInRec(
                    id=emp.id,
                    email=emp.email,
                    full_name=emp.full_name,
                    title=emp.title,
                    department=emp.department,
                    is_active=emp.is_active,
                ),
                score=round(score, 3),
                skill_matches=skill_matches,
                availability_pct=avail_pct,
                explanation=explanation,
                feedback=row.feedback,
            )
        )

    await db.commit()
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _qdrant_search(project: Project, top_k: int) -> list[uuid.UUID]:
    """
    Query Qdrant with the project's skill embedding.
    Returns a list of employee UUIDs ordered by vector similarity.
    Falls back to empty list (triggers full-scan fallback) if Qdrant is unreachable
    or the collection has no vectors yet.
    """
    try:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        query_vector = embed_project_requirements(project)

        client = AsyncQdrantClient(url=settings.qdrant_url)
        hits = await client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )
        return [uuid.UUID(h.payload["employee_id"]) for h in hits if h.payload]
    except Exception:
        logger.warning("Qdrant search unavailable — falling back to full employee scan", exc_info=True)
        return []


async def index_employee_in_qdrant(employee: Employee) -> None:
    """
    Upsert an employee's profile vector into Qdrant.
    Called from sync.py after skills are persisted to PostgreSQL.
    """
    try:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import PointStruct, VectorParams, Distance

        from etip_api.services.embedding import embed_employee_profile

        skill_objects = [es.skill for es in employee.skills]
        vector = embed_employee_profile(employee, skill_objects)

        client = AsyncQdrantClient(url=settings.qdrant_url)

        # Ensure collection exists (idempotent)
        collections = await client.get_collections()
        names = [c.name for c in collections.collections]
        if settings.qdrant_collection not in names:
            await client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=len(vector), distance=Distance.COSINE),
            )

        await client.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                PointStruct(
                    id=str(employee.id),
                    vector=vector,
                    payload={
                        "employee_id": str(employee.id),
                        "tenant_id": str(employee.tenant_id),
                        "full_name": employee.full_name,
                    },
                )
            ],
        )
    except Exception:
        logger.warning("Qdrant indexing failed for employee_id=%s", employee.id, exc_info=True)


def _business_days(start: date, end: date) -> int:
    """Count Mon–Fri days in [start, end] inclusive."""
    if start > end:
        return 0
    total = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            total += 1
        d += timedelta(days=1)
    return total


async def _get_available_pct(
    db: AsyncSession,
    employee_id: uuid.UUID,
    tenant_id: uuid.UUID,
    start_date: object,
    end_date: object,
) -> float:
    if not start_date or not end_date:
        return 100.0  # no dates → assume fully available

    project_busdays = _business_days(start_date, end_date)
    if project_busdays == 0:
        return 100.0  # weekend-only project → treat as fully available

    result = await db.execute(
        select(
            Allocation.start_date,
            Allocation.end_date,
            Allocation.allocation_pct,
        ).where(
            Allocation.tenant_id == tenant_id,
            Allocation.employee_id == employee_id,
            Allocation.start_date <= end_date,
            Allocation.end_date >= start_date,
        )
    )
    rows = result.all()

    total_allocated = 0.0
    for row in rows:
        overlap_start = max(row.start_date, start_date)
        overlap_end = min(row.end_date, end_date)
        overlap_busdays = _business_days(overlap_start, overlap_end)
        weight = overlap_busdays / project_busdays
        total_allocated += row.allocation_pct * weight

    return round(max(0.0, 100.0 - total_allocated), 1)


def _rerank_candidates(
    project: Project,
    candidates: list[tuple[Employee, float, float, list[SkillMatch]]],
) -> list[tuple[Employee, float, float, list[SkillMatch]]]:
    """
    Rerank candidates with a cross-encoder (flashrank ms-marco-MiniLM-L-2-v2, CPU-only).
    Falls back silently to skill-overlap order if flashrank is unavailable or raises.
    """
    if not candidates:
        return candidates
    try:
        from flashrank import RerankRequest

        query = " ".join(
            r.get("skill_label", r.get("label", ""))
            for r in (project.required_skills or [])
        )
        passages = [
            {
                "id": i,
                "text": (
                    f"{emp.full_name or ''} {emp.title or ''}: "
                    + ", ".join(m.skill_label for m in skill_matches if m.matched)
                ),
            }
            for i, (emp, _score, _avail, skill_matches) in enumerate(candidates)
        ]

        ranker = _get_ranker()
        results = ranker.rerank(RerankRequest(query=query, passages=passages))
        return [candidates[r["id"]] for r in results]
    except Exception:
        logger.debug("flashrank rerank unavailable — using skill overlap order", exc_info=True)
        return candidates


def _skill_overlap_score(
    emp: Employee,
    required: list[dict],
) -> tuple[float, list[SkillMatch]]:
    """
    Simple weighted skill overlap score (0.0 – 1.0).
    Each required skill contributes `weight` points if matched.
    Score = matched_weight / total_weight.
    """
    emp_labels = {es.skill.preferred_label.lower() for es in emp.skills}
    emp_uris = {es.skill.esco_uri for es in emp.skills if es.skill.esco_uri}

    total_weight = sum(r.get("weight", 1.0) for r in required)
    matched_weight = 0.0
    skill_matches: list[SkillMatch] = []

    for req in required:
        label = req.get("skill_label", req.get("label", ""))
        uri = req.get("esco_uri")
        weight = req.get("weight", 1.0)

        matched = bool((label.lower() in emp_labels) or (uri and uri in emp_uris))
        if matched:
            matched_weight += weight

        skill_matches.append(
            SkillMatch(
                skill_label=label,
                esco_uri=uri,
                required_level=req.get("level", req.get("nivel")),
                matched=matched,
            )
        )

    score = matched_weight / total_weight if total_weight > 0 else 0.0
    return score, skill_matches
