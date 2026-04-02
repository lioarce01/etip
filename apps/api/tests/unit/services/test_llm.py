"""Tests for etip_api.services.llm — LiteLLM explanation generation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etip_api.schemas.recommendations import SkillMatch


def _make_skill_matches(matched: list[str], missing: list[str]) -> list[SkillMatch]:
    result = []
    for label in matched:
        result.append(SkillMatch(skill_label=label, esco_uri=None, required_level=None, matched=True))
    for label in missing:
        result.append(SkillMatch(skill_label=label, esco_uri=None, required_level=None, matched=False))
    return result


@pytest.fixture
def mock_project():
    p = MagicMock()
    p.name = "Backend Rewrite"
    p.description = "Migrate monolith to microservices in Go"
    p.required_skills = [{"label": "Go"}, {"label": "Docker"}]
    return p


@pytest.fixture
def mock_employee():
    e = MagicMock()
    e.full_name = "Juan Pérez"
    e.title = "Senior Developer"
    return e


class TestGenerateExplanation:
    @pytest.mark.asyncio
    async def test_returns_string_on_success(self, mock_project, mock_employee):
        skill_matches = _make_skill_matches(["Go", "Docker"], [])
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Juan es ideal para este proyecto porque domina Go y Docker."

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)):
            from etip_api.services.llm import generate_explanation
            result = await generate_explanation(mock_project, mock_employee, skill_matches)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_error(self, mock_project, mock_employee):
        skill_matches = _make_skill_matches(["Go"], ["Docker"])

        with patch("litellm.acompletion", new=AsyncMock(side_effect=Exception("API error"))):
            from etip_api.services.llm import generate_explanation
            result = await generate_explanation(mock_project, mock_employee, skill_matches)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_llm_model_returns_none(self, mock_project, mock_employee):
        skill_matches = _make_skill_matches([], [])

        with patch("etip_api.services.llm.settings") as mock_settings:
            mock_settings.llm_model = ""
            from etip_api.services.llm import generate_explanation
            result = await generate_explanation(mock_project, mock_employee, skill_matches)

        assert result is None

    @pytest.mark.asyncio
    async def test_prompt_includes_project_name(self, mock_project, mock_employee):
        skill_matches = _make_skill_matches(["Go"], ["Docker"])
        captured_kwargs = {}

        async def capture_call(**kwargs):
            captured_kwargs.update(kwargs)
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "explanation"
            return mock_response

        with patch("litellm.acompletion", new=capture_call):
            from etip_api.services.llm import generate_explanation
            await generate_explanation(mock_project, mock_employee, skill_matches)

        messages = captured_kwargs.get("messages", [])
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "Backend Rewrite" in user_msg

    @pytest.mark.asyncio
    async def test_prompt_includes_matched_and_missing_skills(self, mock_project, mock_employee):
        skill_matches = _make_skill_matches(["Go"], ["Docker"])
        captured_messages = []

        async def capture_call(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "ok"
            return mock_response

        with patch("litellm.acompletion", new=capture_call):
            from etip_api.services.llm import generate_explanation
            await generate_explanation(mock_project, mock_employee, skill_matches)

        user_msg = next(m["content"] for m in captured_messages if m["role"] == "user")
        assert "Go" in user_msg
        assert "Docker" in user_msg
