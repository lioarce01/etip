"""Tests for /api/v1/projects/{id}/recommendations router."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etip_api.schemas.recommendations import RecommendationOut, SkillMatch
from tests.conftest import EMPLOYEE_ID, PROJECT_ID, TENANT_ID, USER_ID


def _make_recommendation_out() -> RecommendationOut:
    from etip_api.schemas.recommendations import EmployeeInRec
    return RecommendationOut(
        id=uuid.uuid4(),
        employee=EmployeeInRec(
            id=EMPLOYEE_ID,
            email="juan@acme.com",
            full_name="Juan Pérez",
            title="Senior Developer",
            department=None,
            is_active=True,
        ),
        score=0.85,
        skill_matches=[
            SkillMatch(skill_label="Python", esco_uri=None, required_level="senior", matched=True),
            SkillMatch(skill_label="Docker", esco_uri=None, required_level="mid", matched=False),
        ],
        availability_pct=60.0,
        explanation="Juan tiene experiencia sólida en Python.",
        feedback=None,
    )


class TestGetRecommendations:
    @pytest.mark.asyncio
    async def test_returns_recommendation_list(self, client, as_tm, override_db, make_project):
        project = make_project()
        override_db.get.return_value = project

        mock_results = [_make_recommendation_out()]

        with patch("etip_api.routers.recommendations.run_matching", return_value=mock_results):
            with patch("etip_api.services.audit.log_action", new=AsyncMock()):
                resp = await client.get(f"/api/v1/projects/{PROJECT_ID}/recommendations")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["employee"]["full_name"] == "Juan Pérez"
        assert body[0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_includes_skill_matches(self, client, as_tm, override_db, make_project):
        project = make_project()
        override_db.get.return_value = project

        with patch("etip_api.routers.recommendations.run_matching", return_value=[_make_recommendation_out()]):
            with patch("etip_api.services.audit.log_action", new=AsyncMock()):
                resp = await client.get(f"/api/v1/projects/{PROJECT_ID}/recommendations")

        skill_matches = resp.json()[0]["skill_matches"]
        matched = [s for s in skill_matches if s["matched"]]
        missing = [s for s in skill_matches if not s["matched"]]
        assert len(matched) == 1
        assert len(missing) == 1

    @pytest.mark.asyncio
    async def test_project_not_found_returns_404(self, client, as_tm, override_db):
        override_db.get.return_value = None

        resp = await client.get(f"/api/v1/projects/{PROJECT_ID}/recommendations")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_project_returns_404(self, client, as_tm, override_db, make_project):
        """Recommendations for a project belonging to a different tenant must return 404."""
        project = make_project()
        project.tenant_id = uuid.uuid4()  # different tenant
        override_db.get.return_value = project

        resp = await client.get(f"/api/v1/projects/{PROJECT_ID}/recommendations")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_top_k_param_is_forwarded(self, client, as_tm, override_db, make_project):
        project = make_project()
        override_db.get.return_value = project
        captured_kwargs = {}

        async def capture(**kwargs):
            captured_kwargs.update(kwargs)
            return []

        with patch("etip_api.routers.recommendations.run_matching", side_effect=capture):
            with patch("etip_api.services.audit.log_action", new=AsyncMock()):
                await client.get(f"/api/v1/projects/{PROJECT_ID}/recommendations?top_k=5")

        assert captured_kwargs.get("top_k") == 5

    @pytest.mark.asyncio
    async def test_invalid_top_k_returns_422(self, client, as_tm, override_db):
        resp = await client.get(f"/api/v1/projects/{PROJECT_ID}/recommendations?top_k=0")
        assert resp.status_code == 422


class TestSubmitFeedback:
    @pytest.mark.asyncio
    async def test_accepted_feedback_stored(self, client, as_tm, override_db):
        from etip_api.models.recommendation import Recommendation

        rec = Recommendation()
        rec.id = uuid.uuid4()
        rec.project_id = PROJECT_ID
        rec.tenant_id = TENANT_ID
        rec.employee_id = EMPLOYEE_ID
        rec.score = 0.9
        override_db.get.return_value = rec

        with patch("etip_api.services.audit.log_action", new=AsyncMock()):
            resp = await client.post(
                f"/api/v1/projects/{PROJECT_ID}/recommendations/{rec.id}/feedback",
                json={"feedback": "accepted", "reason": "Great fit"},
            )

        assert resp.status_code == 204
        assert rec.feedback == "accepted"
        assert rec.feedback_reason == "Great fit"

    @pytest.mark.asyncio
    async def test_invalid_feedback_value_returns_422(self, client, as_tm, override_db):
        resp = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/recommendations/{uuid.uuid4()}/feedback",
            json={"feedback": "dunno"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_recommendation_not_found_returns_404(self, client, as_tm, override_db):
        override_db.get.return_value = None

        resp = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/recommendations/{uuid.uuid4()}/feedback",
            json={"feedback": "rejected"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_recommendation_returns_404(self, client, as_tm, override_db):
        """A recommendation from a different tenant must be invisible."""
        from etip_api.models.recommendation import Recommendation

        rec = Recommendation()
        rec.id = uuid.uuid4()
        rec.project_id = PROJECT_ID
        rec.tenant_id = uuid.uuid4()  # different tenant
        rec.employee_id = EMPLOYEE_ID
        override_db.get.return_value = rec

        resp = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/recommendations/{rec.id}/feedback",
            json={"feedback": "accepted"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_recommendation_wrong_project_returns_404(self, client, as_tm, override_db):
        from etip_api.models.recommendation import Recommendation

        rec = Recommendation()
        rec.id = uuid.uuid4()
        rec.project_id = uuid.uuid4()   # different project
        rec.tenant_id = TENANT_ID
        rec.employee_id = EMPLOYEE_ID
        override_db.get.return_value = rec

        resp = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/recommendations/{rec.id}/feedback",
            json={"feedback": "maybe"},
        )
        assert resp.status_code == 404
