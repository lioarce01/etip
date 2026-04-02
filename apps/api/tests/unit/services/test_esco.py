"""Tests for etip_api.services.esco — ESCO skill normalization."""

from unittest.mock import MagicMock, patch

import pytest


class TestNormalizeSkill:
    def setup_method(self):
        # Clear the in-process cache between tests
        from etip_api.services import esco
        esco._cache.clear()

    def test_successful_lookup_returns_uri_and_label(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "_embedded": {
                "results": [
                    {"uri": "http://data.europa.eu/esco/skill/python-123", "title": "Python (programming language)"}
                ]
            }
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            from etip_api.services.esco import normalize_skill
            result = normalize_skill("python3")

        assert result is not None
        assert result["uri"] == "http://data.europa.eu/esco/skill/python-123"
        assert result["preferred_label"] == "Python (programming language)"

    def test_no_results_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"_embedded": {"results": []}}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            from etip_api.services.esco import normalize_skill
            result = normalize_skill("unknownskillxyz")

        assert result is None

    def test_api_error_returns_none(self):
        with patch("httpx.get", side_effect=Exception("timeout")):
            from etip_api.services.esco import normalize_skill
            result = normalize_skill("python")

        assert result is None

    def test_cache_hit_skips_api_call(self):
        from etip_api.services import esco

        esco._cache["cached-skill"] = {"uri": "http://cached", "preferred_label": "Cached Skill"}

        with patch("httpx.Client") as mock_client_cls:
            from etip_api.services.esco import normalize_skill
            result = normalize_skill("cached-skill")

        mock_client_cls.assert_not_called()
        assert result["uri"] == "http://cached"

    def test_input_is_lowercased_for_cache_key(self):
        from etip_api.services import esco

        esco._cache["python"] = {"uri": "http://python-uri", "preferred_label": "Python"}

        from etip_api.services.esco import normalize_skill
        result1 = normalize_skill("Python")
        result2 = normalize_skill("PYTHON")

        assert result1 == result2
        assert result1["uri"] == "http://python-uri"
