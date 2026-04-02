"""Tests for etip_api.services.matching — scoring and availability logic."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects.postgresql import Insert

from etip_api.services.matching import _business_days, _get_available_pct, _skill_overlap_score
from etip_api.schemas.recommendations import SkillMatch


# ── _business_days ─────────────────────────────────────────────────────────────

class TestBusinessDays:
    def test_single_weekday(self):
        # 2026-04-01 is a Wednesday
        assert _business_days(date(2026, 4, 1), date(2026, 4, 1)) == 1

    def test_single_weekend_day(self):
        # 2026-04-04 is a Saturday
        assert _business_days(date(2026, 4, 4), date(2026, 4, 4)) == 0

    def test_full_work_week(self):
        # Mon 2026-03-30 to Fri 2026-04-03
        assert _business_days(date(2026, 3, 30), date(2026, 4, 3)) == 5

    def test_week_including_weekend(self):
        # Mon 2026-03-30 to Sun 2026-04-05 → still 5 business days
        assert _business_days(date(2026, 3, 30), date(2026, 4, 5)) == 5

    def test_start_after_end_returns_zero(self):
        assert _business_days(date(2026, 4, 5), date(2026, 4, 1)) == 0

    def test_weekend_only_range(self):
        # Sat–Sun 2026-04-04 to 2026-04-05
        assert _business_days(date(2026, 4, 4), date(2026, 4, 5)) == 0

    def test_two_weeks(self):
        # Mon 2026-03-30 to Fri 2026-04-10 = 10 business days
        assert _business_days(date(2026, 3, 30), date(2026, 4, 10)) == 10


# ── _skill_overlap_score ───────────────────────────────────────────────────────

class TestSkillOverlapScore:
    def test_full_match_returns_one(self, make_employee, make_employee_skill):
        emp = make_employee(skills=["Python", "FastAPI"])
        required = [
            {"label": "Python", "esco_uri": None, "nivel": "senior", "weight": 1.0},
            {"label": "FastAPI", "esco_uri": None, "nivel": "mid", "weight": 1.0},
        ]
        score, matches = _skill_overlap_score(emp, required)
        assert score == 1.0
        assert all(m.matched for m in matches)

    def test_no_match_returns_zero(self, make_employee):
        emp = make_employee(skills=["Java", "Spring"])
        required = [
            {"label": "Python", "esco_uri": None, "nivel": "senior", "weight": 1.0},
            {"label": "FastAPI", "esco_uri": None, "nivel": "mid", "weight": 1.0},
        ]
        score, matches = _skill_overlap_score(emp, required)
        assert score == 0.0
        assert not any(m.matched for m in matches)

    def test_partial_match_scores_proportionally(self, make_employee):
        emp = make_employee(skills=["Python"])
        required = [
            {"label": "Python", "esco_uri": None, "nivel": "senior", "weight": 1.0},
            {"label": "FastAPI", "esco_uri": None, "nivel": "mid", "weight": 1.0},
        ]
        score, matches = _skill_overlap_score(emp, required)
        assert score == 0.5
        assert matches[0].matched is True   # Python
        assert matches[1].matched is False  # FastAPI

    def test_weighted_skills_affect_score(self, make_employee):
        emp = make_employee(skills=["Python"])
        required = [
            {"label": "Python", "esco_uri": None, "nivel": "senior", "weight": 2.0},  # high value
            {"label": "FastAPI", "esco_uri": None, "nivel": "mid", "weight": 1.0},
        ]
        score, _ = _skill_overlap_score(emp, required)
        # Python (weight 2) matched out of total 3 = 0.667
        assert round(score, 3) == pytest.approx(2 / 3, rel=0.01)

    def test_esco_uri_match(self, make_employee_skill, make_employee):
        uri = "http://data.europa.eu/esco/skill/python-123"

        # Give the employee a skill with the ESCO URI
        es = make_employee_skill(label="Python")
        es.skill.esco_uri = uri
        emp = make_employee(skills=[])
        emp.skills = [es]

        required = [{"label": "Something Else", "esco_uri": uri, "nivel": None, "weight": 1.0}]
        score, matches = _skill_overlap_score(emp, required)
        assert score == 1.0
        assert matches[0].matched is True

    def test_empty_required_skills_returns_zero(self, make_employee):
        emp = make_employee(skills=["Python"])
        score, matches = _skill_overlap_score(emp, [])
        assert score == 0.0
        assert matches == []

    def test_skill_labels_are_case_insensitive(self, make_employee):
        emp = make_employee(skills=["Python"])  # stored as "Python"
        required = [{"label": "python", "esco_uri": None, "nivel": None, "weight": 1.0}]
        score, matches = _skill_overlap_score(emp, required)
        assert score == 1.0
        assert matches[0].matched is True


# ── _get_available_pct ─────────────────────────────────────────────────────────

def _make_alloc_row(start: date, end: date, pct: float):
    row = MagicMock()
    row.start_date = start
    row.end_date = end
    row.allocation_pct = pct
    return row


class TestGetAvailablePct:
    @pytest.mark.asyncio
    async def test_no_dates_returns_100(self, mock_db):
        pct = await _get_available_pct(mock_db, uuid.uuid4(), uuid.uuid4(), None, None)
        assert pct == 100.0

    @pytest.mark.asyncio
    async def test_no_allocations_returns_100(self, mock_db):
        mock_db.execute.return_value.all.return_value = []
        pct = await _get_available_pct(
            mock_db, uuid.uuid4(), uuid.uuid4(), date(2026, 4, 1), date(2026, 4, 10)
        )
        assert pct == 100.0

    @pytest.mark.asyncio
    async def test_fully_allocated_returns_zero(self, mock_db):
        # Allocation covers the full project period
        row = _make_alloc_row(date(2026, 4, 1), date(2026, 4, 10), 100.0)
        mock_db.execute.return_value.all.return_value = [row]
        pct = await _get_available_pct(
            mock_db, uuid.uuid4(), uuid.uuid4(), date(2026, 4, 1), date(2026, 4, 10)
        )
        assert pct == 0.0

    @pytest.mark.asyncio
    async def test_partial_allocation(self, mock_db):
        # 60% allocation covering full project → 40% available
        row = _make_alloc_row(date(2026, 4, 1), date(2026, 4, 10), 60.0)
        mock_db.execute.return_value.all.return_value = [row]
        pct = await _get_available_pct(
            mock_db, uuid.uuid4(), uuid.uuid4(), date(2026, 4, 1), date(2026, 4, 10)
        )
        assert pct == 40.0

    @pytest.mark.asyncio
    async def test_over_allocated_clamped_to_zero(self, mock_db):
        # Two full-period allocations summing to 120% → clamped to 0
        row1 = _make_alloc_row(date(2026, 4, 1), date(2026, 4, 10), 80.0)
        row2 = _make_alloc_row(date(2026, 4, 1), date(2026, 4, 10), 40.0)
        mock_db.execute.return_value.all.return_value = [row1, row2]
        pct = await _get_available_pct(
            mock_db, uuid.uuid4(), uuid.uuid4(), date(2026, 4, 1), date(2026, 4, 10)
        )
        assert pct == 0.0

    @pytest.mark.asyncio
    async def test_weekend_only_project_returns_100(self, mock_db):
        # 2026-04-04 (Sat) to 2026-04-05 (Sun) = 0 business days → fully available
        pct = await _get_available_pct(
            mock_db, uuid.uuid4(), uuid.uuid4(), date(2026, 4, 4), date(2026, 4, 5)
        )
        assert pct == 100.0
        # DB should not be queried since project_busdays == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_allocation_only_over_weekend_of_project(self, mock_db):
        # Project: Mon 2026-03-30 to Fri 2026-04-03 (5 business days)
        # Allocation: Sat 2026-04-04 to Sun 2026-04-05 — overlaps by date range
        # but the overlap period (Apr 4–5) has 0 business days → weight = 0 → still 100% available
        row = _make_alloc_row(date(2026, 4, 4), date(2026, 4, 5), 100.0)
        mock_db.execute.return_value.all.return_value = [row]
        pct = await _get_available_pct(
            mock_db, uuid.uuid4(), uuid.uuid4(), date(2026, 3, 30), date(2026, 4, 3)
        )
        assert pct == 100.0

    @pytest.mark.asyncio
    async def test_partial_date_overlap_weighted(self, mock_db):
        # Project: Mon 2026-03-30 to Fri 2026-04-10 (10 business days)
        # Allocation: Mon 2026-03-30 to Fri 2026-04-03 (5 business days) at 100%
        # weight = 5/10 = 0.5 → allocated = 50% → available = 50%
        row = _make_alloc_row(date(2026, 3, 30), date(2026, 4, 3), 100.0)
        mock_db.execute.return_value.all.return_value = [row]
        pct = await _get_available_pct(
            mock_db, uuid.uuid4(), uuid.uuid4(), date(2026, 3, 30), date(2026, 4, 10)
        )
        assert pct == 50.0

    @pytest.mark.asyncio
    async def test_query_filters_by_tenant_id(self, mock_db):
        """The SELECT must include a tenant_id WHERE clause to prevent cross-tenant leakage."""
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        mock_db.execute.return_value.all.return_value = []
        tenant_id = uuid.uuid4()
        employee_id = uuid.uuid4()

        await _get_available_pct(
            mock_db, employee_id, tenant_id, date(2026, 4, 1), date(2026, 4, 10)
        )

        stmt = mock_db.execute.call_args[0][0]
        compiled = stmt.compile(dialect=pg_dialect())
        sql = str(compiled)
        assert "tenant_id" in sql


# ── run_matching upsert ────────────────────────────────────────────────────────

class TestRunMatchingUpsert:
    @pytest.mark.asyncio
    async def test_uses_pg_insert_not_db_add(self, mock_db, make_project, make_employee):
        """run_matching must use INSERT ON CONFLICT, never db.add()."""
        from etip_api.services.matching import run_matching

        project = make_project(required_skills=[
            {"label": "Python", "esco_uri": None, "nivel": "senior", "weight": 1.0},
        ])
        project.start_date = None
        project.end_date = None

        emp = make_employee(skills=["Python"])

        emp_result = MagicMock()
        emp_result.scalars.return_value.all.return_value = [emp]

        upsert_row = MagicMock()
        upsert_row.id = uuid.uuid4()
        upsert_row.feedback = None
        upsert_result = MagicMock()
        upsert_result.one.return_value = upsert_row

        mock_db.execute = AsyncMock(side_effect=[emp_result, upsert_result])

        with patch("etip_api.services.matching._qdrant_search", return_value=[]):
            with patch("etip_api.services.matching.generate_explanation", return_value="great match"):
                results = await run_matching(db=mock_db, project=project, top_k=1)

        assert results
        mock_db.add.assert_not_called()
        second_stmt = mock_db.execute.call_args_list[1][0][0]
        assert isinstance(second_stmt, Insert)

    @pytest.mark.asyncio
    async def test_upsert_preserves_existing_feedback(self, mock_db, make_project, make_employee):
        """Feedback from a previous run must come from the RETURNING clause."""
        from etip_api.services.matching import run_matching

        project = make_project()
        project.start_date = None
        project.end_date = None
        emp = make_employee(skills=["Python", "FastAPI"])

        emp_result = MagicMock()
        emp_result.scalars.return_value.all.return_value = [emp]

        upsert_row = MagicMock()
        upsert_row.id = uuid.uuid4()
        upsert_row.feedback = "accepted"
        upsert_result = MagicMock()
        upsert_result.one.return_value = upsert_row

        mock_db.execute = AsyncMock(side_effect=[emp_result, upsert_result])

        with patch("etip_api.services.matching._qdrant_search", return_value=[]):
            with patch("etip_api.services.matching.generate_explanation", return_value=None):
                results = await run_matching(db=mock_db, project=project, top_k=1)

        assert results[0].feedback == "accepted"


class TestRerankCandidates:
    def _make_candidate(self, name: str, skill_labels: list[str], score: float = 0.5):
        from etip_api.schemas.recommendations import SkillMatch

        emp = MagicMock()
        emp.full_name = name
        emp.title = "Engineer"
        skill_matches = [
            SkillMatch(skill_label=s, esco_uri=None, required_level=None, matched=True)
            for s in skill_labels
        ]
        return (emp, score, 80.0, skill_matches)

    def _make_project(self, skill_labels: list[str]):
        project = MagicMock()
        project.required_skills = [{"skill_label": s, "weight": 1.0} for s in skill_labels]
        return project

    def test_rerank_reorders_candidates(self, make_employee):
        """When flashrank returns a reversed order, _rerank_candidates applies it."""
        from etip_api.services.matching import _rerank_candidates

        c1 = self._make_candidate("Alice", ["Python"])
        c2 = self._make_candidate("Bob", ["FastAPI"])
        project = self._make_project(["Python", "FastAPI"])

        # flashrank returns Bob first (id=1), then Alice (id=0)
        mock_results = [{"id": 1, "score": 0.9}, {"id": 0, "score": 0.7}]

        with patch("etip_api.services.matching._get_ranker") as mock_get_ranker:
            mock_ranker = MagicMock()
            mock_ranker.rerank.return_value = mock_results
            mock_get_ranker.return_value = mock_ranker

            result = _rerank_candidates(project, [c1, c2])

        assert result[0][0].full_name == "Bob"
        assert result[1][0].full_name == "Alice"

    def test_rerank_fallback_on_exception(self):
        """When flashrank raises, original order is preserved."""
        from etip_api.services.matching import _rerank_candidates

        c1 = self._make_candidate("Alice", ["Python"])
        c2 = self._make_candidate("Bob", ["FastAPI"])
        project = self._make_project(["Python"])

        with patch("etip_api.services.matching._get_ranker", side_effect=RuntimeError("model unavailable")):
            result = _rerank_candidates(project, [c1, c2])

        assert result[0][0].full_name == "Alice"
        assert result[1][0].full_name == "Bob"

    def test_rerank_empty_candidates_returns_empty(self):
        """Empty candidate list must be returned as-is without calling flashrank."""
        from etip_api.services.matching import _rerank_candidates

        project = self._make_project(["Python"])
        with patch("etip_api.services.matching._get_ranker") as mock_get_ranker:
            result = _rerank_candidates(project, [])
        mock_get_ranker.assert_not_called()
        assert result == []


class TestRecommendationModelConstraint:
    def test_unique_constraint_on_project_employee(self):
        from etip_api.models.recommendation import Recommendation
        from sqlalchemy import UniqueConstraint

        constraints = {type(c).__name__: c for c in Recommendation.__table_args__}
        assert "UniqueConstraint" in constraints
        uc = constraints["UniqueConstraint"]
        col_names = [c.name for c in uc.columns]
        assert "project_id" in col_names
        assert "employee_id" in col_names
