"""Tests for etip_api.services.embedding — fastembed local embeddings."""

from unittest.mock import MagicMock, patch

import pytest
import numpy as np


def _mock_fastembed_model(dim: int = 384):
    """Returns a mock TextEmbedding that yields fixed-size numpy arrays."""
    model = MagicMock()
    model.embed.side_effect = lambda texts: (np.ones(dim) for _ in texts)
    return model


class TestEmbedTexts:
    def test_returns_list_of_float_lists(self):
        with patch("etip_api.services.embedding._get_embedding_model", return_value=_mock_fastembed_model()):
            from etip_api.services.embedding import embed_texts
            result = embed_texts(["hello", "world"])

        assert len(result) == 2
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])

    def test_vector_dimension(self):
        with patch("etip_api.services.embedding._get_embedding_model", return_value=_mock_fastembed_model(384)):
            from etip_api.services.embedding import embed_texts
            result = embed_texts(["hello"])

        assert len(result[0]) == 384

    def test_empty_list_returns_empty(self):
        model = MagicMock()
        model.embed.return_value = iter([])

        with patch("etip_api.services.embedding._get_embedding_model", return_value=model):
            from etip_api.services.embedding import embed_texts
            result = embed_texts([])

        assert result == []


class TestEmbedOne:
    def test_returns_single_vector(self):
        with patch("etip_api.services.embedding._get_embedding_model", return_value=_mock_fastembed_model()):
            from etip_api.services.embedding import embed_one
            result = embed_one("test text")

        assert isinstance(result, list)
        assert len(result) == 384


class TestEmbedEmployeeProfile:
    def test_combines_name_title_department_skills(self):
        emp = MagicMock()
        emp.full_name = "Juan Pérez"
        emp.title = "Senior Developer"
        emp.department = "Engineering"

        skill1 = MagicMock()
        skill1.preferred_label = "Python"
        skill2 = MagicMock()
        skill2.preferred_label = "FastAPI"

        captured_texts = []

        def fake_embed(texts):
            captured_texts.extend(texts)
            return [np.ones(384)]

        mock_model = MagicMock()
        mock_model.embed.side_effect = fake_embed

        with patch("etip_api.services.embedding._get_embedding_model", return_value=mock_model):
            from etip_api.services.embedding import embed_employee_profile
            embed_employee_profile(emp, [skill1, skill2])

        assert len(captured_texts) == 1
        profile_text = captured_texts[0]
        assert "Juan Pérez" in profile_text
        assert "Senior Developer" in profile_text
        assert "Python" in profile_text
        assert "FastAPI" in profile_text

    def test_empty_skills_still_works(self):
        emp = MagicMock()
        emp.full_name = "Jane"
        emp.title = None
        emp.department = None

        with patch("etip_api.services.embedding._get_embedding_model", return_value=_mock_fastembed_model()):
            from etip_api.services.embedding import embed_employee_profile
            result = embed_employee_profile(emp, [])

        assert isinstance(result, list)


class TestEmbedProjectRequirements:
    def test_includes_project_name_and_skills(self):
        project = MagicMock()
        project.name = "Backend Rewrite"
        project.description = "Go microservices"
        project.required_skills = [
            {"label": "Go", "nivel": "senior"},
            {"label": "Docker", "nivel": "mid"},
        ]

        captured = []

        def fake_embed(texts):
            captured.extend(texts)
            return [np.ones(384)]

        mock_model = MagicMock()
        mock_model.embed.side_effect = fake_embed

        with patch("etip_api.services.embedding._get_embedding_model", return_value=mock_model):
            from etip_api.services.embedding import embed_project_requirements
            embed_project_requirements(project)

        query_text = captured[0]
        assert "Backend Rewrite" in query_text
        assert "Go" in query_text
        assert "Docker" in query_text

    def test_no_required_skills_still_works(self):
        project = MagicMock()
        project.name = "Empty Project"
        project.description = None
        project.required_skills = []

        with patch("etip_api.services.embedding._get_embedding_model", return_value=_mock_fastembed_model()):
            from etip_api.services.embedding import embed_project_requirements
            result = embed_project_requirements(project)

        assert isinstance(result, list)
