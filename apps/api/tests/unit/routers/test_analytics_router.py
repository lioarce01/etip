"""Tests for /api/v1/analytics router."""

from unittest.mock import MagicMock

import pytest

from tests.conftest import TENANT_ID, USER_ID


class TestAnalyticsEndpoint:
    @pytest.mark.asyncio
    async def test_analytics_returns_200_for_tm(self, client, as_tm, override_db):
        """TM role can access analytics endpoint."""
        # Mock all db.execute calls
        # Call 1: total_employees count
        mock_emp_count = MagicMock()
        mock_emp_count.scalar_one.return_value = 10

        # Call 2: total_projects count
        mock_proj_count = MagicMock()
        mock_proj_count.scalar_one.return_value = 5

        # Call 3: feedback counts (GROUP BY)
        mock_feedback_rows = MagicMock()
        mock_feedback_rows.all.return_value = [
            ("accepted", 3),
            ("rejected", 2),
            ("maybe", 1),
            (None, 1),
        ]

        # Call 4: project IDs for precision@5
        mock_proj_ids = MagicMock()
        mock_proj_ids.all.return_value = [(1,), (2,)]

        # Call 5+: top-5 recs per project (2 projects)
        mock_top_5_p1 = MagicMock()
        mock_top_5_p1.scalars.return_value.all.return_value = [
            "accepted",
            "accepted",
            "rejected",
            "accepted",
            "maybe",
        ]

        mock_top_5_p2 = MagicMock()
        mock_top_5_p2.scalars.return_value.all.return_value = [
            "accepted",
            "rejected",
            "rejected",
            "maybe",
            "accepted",
        ]

        # Call 7: project IDs for precision@10
        mock_proj_ids_p10 = MagicMock()
        mock_proj_ids_p10.all.return_value = [(1,), (2,)]

        # Call 8+: top-10 recs per project (2 projects, but limited <10)
        mock_top_10_p1 = MagicMock()
        mock_top_10_p1.scalars.return_value.all.return_value = [
            "accepted",
            "accepted",
            "rejected",
            "accepted",
        ]  # 4 recs < 10, skip

        mock_top_10_p2 = MagicMock()
        mock_top_10_p2.scalars.return_value.all.return_value = [
            "accepted",
            "rejected",
            "rejected",
        ]  # 3 recs < 10, skip

        override_db.execute.side_effect = [
            mock_emp_count,
            mock_proj_count,
            mock_feedback_rows,
            mock_proj_ids,
            mock_top_5_p1,
            mock_top_5_p2,
            mock_proj_ids_p10,
            mock_top_10_p1,
            mock_top_10_p2,
        ]

        resp = await client.get("/api/v1/analytics")
        assert resp.status_code == 200

        body = resp.json()
        assert body["total_employees"] == 10
        assert body["total_projects"] == 5
        assert body["total_recommendations"] == 7  # 3+2+1+1
        assert body["accepted_count"] == 3
        assert body["rejected_count"] == 2
        assert body["maybe_count"] == 1
        assert body["no_feedback_count"] == 1

    @pytest.mark.asyncio
    async def test_analytics_returns_200_for_admin(self, client, as_admin, override_db):
        """Admin role can access analytics endpoint."""
        # Minimal mock setup
        mock_emp_count = MagicMock()
        mock_emp_count.scalar_one.return_value = 0

        mock_proj_count = MagicMock()
        mock_proj_count.scalar_one.return_value = 0

        mock_feedback_rows = MagicMock()
        mock_feedback_rows.all.return_value = []

        mock_proj_ids = MagicMock()
        mock_proj_ids.all.return_value = []

        mock_proj_ids_p10 = MagicMock()
        mock_proj_ids_p10.all.return_value = []

        override_db.execute.side_effect = [
            mock_emp_count,
            mock_proj_count,
            mock_feedback_rows,
            mock_proj_ids,
            mock_proj_ids_p10,
        ]

        resp = await client.get("/api/v1/analytics")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_analytics_dev_forbidden(self, client, as_dev, override_db):
        """Dev role cannot access analytics endpoint."""
        resp = await client.get("/api/v1/analytics")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_analytics_empty_state(self, client, as_tm, override_db):
        """Empty analytics returns all zeros without crash."""
        mock_emp_count = MagicMock()
        mock_emp_count.scalar_one.return_value = 0

        mock_proj_count = MagicMock()
        mock_proj_count.scalar_one.return_value = 0

        mock_feedback_rows = MagicMock()
        mock_feedback_rows.all.return_value = []

        mock_proj_ids = MagicMock()
        mock_proj_ids.all.return_value = []

        mock_proj_ids_p10 = MagicMock()
        mock_proj_ids_p10.all.return_value = []

        override_db.execute.side_effect = [
            mock_emp_count,
            mock_proj_count,
            mock_feedback_rows,
            mock_proj_ids,
            mock_proj_ids_p10,
        ]

        resp = await client.get("/api/v1/analytics")
        assert resp.status_code == 200

        body = resp.json()
        assert body["total_employees"] == 0
        assert body["total_projects"] == 0
        assert body["total_recommendations"] == 0
        assert body["accepted_count"] == 0
        assert body["rejected_count"] == 0
        assert body["maybe_count"] == 0
        assert body["no_feedback_count"] == 0
        assert body["precision_at_5"] == 0.0
        assert body["precision_at_10"] == 0.0
        assert body["acceptance_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_acceptance_rate_calculation(self, client, as_tm, override_db):
        """Acceptance rate = accepted / (accepted + rejected + maybe)."""
        mock_emp_count = MagicMock()
        mock_emp_count.scalar_one.return_value = 10

        mock_proj_count = MagicMock()
        mock_proj_count.scalar_one.return_value = 1

        # 3 accepted, 2 rejected, 0 maybe => rate = 3 / 5 = 0.6
        mock_feedback_rows = MagicMock()
        mock_feedback_rows.all.return_value = [
            ("accepted", 3),
            ("rejected", 2),
        ]

        mock_proj_ids = MagicMock()
        mock_proj_ids.all.return_value = [(1,)]

        mock_top_5 = MagicMock()
        mock_top_5.scalars.return_value.all.return_value = [
            "accepted",
            "accepted",
            "accepted",
            "rejected",
            "rejected",
        ]

        mock_proj_ids_p10 = MagicMock()
        mock_proj_ids_p10.all.return_value = [(1,)]

        mock_top_10 = MagicMock()
        mock_top_10.scalars.return_value.all.return_value = [
            "accepted",
            "accepted",
            "accepted",
            "rejected",
            "rejected",
        ]

        override_db.execute.side_effect = [
            mock_emp_count,
            mock_proj_count,
            mock_feedback_rows,
            mock_proj_ids,
            mock_top_5,
            mock_proj_ids_p10,
            mock_top_10,
        ]

        resp = await client.get("/api/v1/analytics")
        assert resp.status_code == 200

        body = resp.json()
        assert body["accepted_count"] == 3
        assert body["rejected_count"] == 2
        assert body["maybe_count"] == 0
        assert body["no_feedback_count"] == 0
        assert body["acceptance_rate"] == 0.6

    @pytest.mark.asyncio
    async def test_acceptance_rate_zero_when_no_feedback(self, client, as_tm, override_db):
        """Acceptance rate = 0.0 when no feedback given."""
        mock_emp_count = MagicMock()
        mock_emp_count.scalar_one.return_value = 5

        mock_proj_count = MagicMock()
        mock_proj_count.scalar_one.return_value = 2

        # Only no_feedback records
        mock_feedback_rows = MagicMock()
        mock_feedback_rows.all.return_value = [(None, 3)]

        mock_proj_ids = MagicMock()
        mock_proj_ids.all.return_value = [(1,), (2,)]

        mock_top_5_p1 = MagicMock()
        mock_top_5_p1.scalars.return_value.all.return_value = []

        mock_top_5_p2 = MagicMock()
        mock_top_5_p2.scalars.return_value.all.return_value = []

        mock_proj_ids_p10 = MagicMock()
        mock_proj_ids_p10.all.return_value = [(1,), (2,)]

        mock_top_10_p1 = MagicMock()
        mock_top_10_p1.scalars.return_value.all.return_value = []

        mock_top_10_p2 = MagicMock()
        mock_top_10_p2.scalars.return_value.all.return_value = []

        override_db.execute.side_effect = [
            mock_emp_count,
            mock_proj_count,
            mock_feedback_rows,
            mock_proj_ids,
            mock_top_5_p1,
            mock_top_5_p2,
            mock_proj_ids_p10,
            mock_top_10_p1,
            mock_top_10_p2,
        ]

        resp = await client.get("/api/v1/analytics")
        assert resp.status_code == 200

        body = resp.json()
        assert body["accepted_count"] == 0
        assert body["rejected_count"] == 0
        assert body["maybe_count"] == 0
        assert body["no_feedback_count"] == 3
        assert body["acceptance_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_no_feedback_count_correct(self, client, as_tm, override_db):
        """Recommendations with feedback=None counted as no_feedback_count."""
        mock_emp_count = MagicMock()
        mock_emp_count.scalar_one.return_value = 10

        mock_proj_count = MagicMock()
        mock_proj_count.scalar_one.return_value = 1

        # Mix of feedback and None
        mock_feedback_rows = MagicMock()
        mock_feedback_rows.all.return_value = [
            ("accepted", 2),
            (None, 3),  # no feedback
        ]

        mock_proj_ids = MagicMock()
        mock_proj_ids.all.return_value = [(1,)]

        mock_top_5 = MagicMock()
        mock_top_5.scalars.return_value.all.return_value = ["accepted", "accepted"]

        mock_proj_ids_p10 = MagicMock()
        mock_proj_ids_p10.all.return_value = [(1,)]

        mock_top_10 = MagicMock()
        mock_top_10.scalars.return_value.all.return_value = ["accepted", "accepted"]

        override_db.execute.side_effect = [
            mock_emp_count,
            mock_proj_count,
            mock_feedback_rows,
            mock_proj_ids,
            mock_top_5,
            mock_proj_ids_p10,
            mock_top_10,
        ]

        resp = await client.get("/api/v1/analytics")
        assert resp.status_code == 200

        body = resp.json()
        assert body["accepted_count"] == 2
        assert body["no_feedback_count"] == 3

    @pytest.mark.asyncio
    async def test_precision_at_5_skips_insufficient_projects(
        self, client, as_tm, override_db
    ):
        """Projects with <5 recommendations skipped in precision@5 calc."""
        mock_emp_count = MagicMock()
        mock_emp_count.scalar_one.return_value = 10

        mock_proj_count = MagicMock()
        mock_proj_count.scalar_one.return_value = 2

        # 2 accepted, 0 rejected (no feedback)
        mock_feedback_rows = MagicMock()
        mock_feedback_rows.all.return_value = [("accepted", 2)]

        # 2 projects
        mock_proj_ids = MagicMock()
        mock_proj_ids.all.return_value = [(1,), (2,)]

        # Project 1: only 3 recs (< 5, skip)
        mock_top_5_p1 = MagicMock()
        mock_top_5_p1.scalars.return_value.all.return_value = [
            "accepted",
            "accepted",
            "rejected",
        ]

        # Project 2: no recs (< 5, skip)
        mock_top_5_p2 = MagicMock()
        mock_top_5_p2.scalars.return_value.all.return_value = []

        # precision@10
        mock_proj_ids_p10 = MagicMock()
        mock_proj_ids_p10.all.return_value = [(1,), (2,)]

        mock_top_10_p1 = MagicMock()
        mock_top_10_p1.scalars.return_value.all.return_value = []

        mock_top_10_p2 = MagicMock()
        mock_top_10_p2.scalars.return_value.all.return_value = []

        override_db.execute.side_effect = [
            mock_emp_count,
            mock_proj_count,
            mock_feedback_rows,
            mock_proj_ids,
            mock_top_5_p1,
            mock_top_5_p2,
            mock_proj_ids_p10,
            mock_top_10_p1,
            mock_top_10_p2,
        ]

        resp = await client.get("/api/v1/analytics")
        assert resp.status_code == 200

        body = resp.json()
        # No projects qualify (both < 5 recs), so precision_at_5 = 0.0
        assert body["precision_at_5"] == 0.0
