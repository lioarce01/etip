"""Tests for Redis caching in etip_api.services.llm.generate_explanation."""

import uuid
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
def project_id():
    return uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


@pytest.fixture
def employee_id():
    return uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")


@pytest.fixture
def mock_project(project_id):
    p = MagicMock()
    p.id = project_id
    p.name = "Backend Rewrite"
    p.description = "Migrate monolith to microservices"
    return p


@pytest.fixture
def mock_employee(employee_id):
    e = MagicMock()
    e.id = employee_id
    e.full_name = "Juan Pérez"
    e.title = "Senior Developer"
    return e


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)   # default: cache miss
    r.set = AsyncMock(return_value=True)
    return r


@pytest.fixture
def llm_response():
    resp = MagicMock()
    resp.choices[0].message.content = "Juan es ideal para este proyecto."
    return resp


class TestLLMExplanationCaching:
    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm_and_caches_result(
        self, mock_project, mock_employee, mock_redis, llm_response, project_id, employee_id
    ):
        """On a cache miss the LLM is called and the result is written to Redis."""
        skill_matches = _make_skill_matches(["Python"], [])

        with (
            patch("etip_api.services.llm._get_redis", return_value=mock_redis),
            patch("litellm.acompletion", new=AsyncMock(return_value=llm_response)),
            patch("etip_api.services.llm.settings") as mock_settings,
        ):
            mock_settings.llm_model = "groq/llama-3.3-70b-versatile"
            mock_settings.groq_api_key = "test-key"
            mock_settings.openai_api_key = ""
            mock_settings.anthropic_api_key = ""
            mock_settings.llm_explanation_cache_ttl = 86400

            from etip_api.services.llm import generate_explanation
            result = await generate_explanation(mock_project, mock_employee, skill_matches)

        assert result == "Juan es ideal para este proyecto."
        mock_redis.get.assert_awaited_once_with(f"llm:explanation:{project_id}:{employee_id}")
        mock_redis.set.assert_awaited_once_with(
            f"llm:explanation:{project_id}:{employee_id}",
            "Juan es ideal para este proyecto.",
            ex=86400,
        )

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_skips_llm(
        self, mock_project, mock_employee, mock_redis, project_id, employee_id
    ):
        """On a cache hit the LLM must NOT be called."""
        mock_redis.get = AsyncMock(return_value="Cached explanation text.")
        skill_matches = _make_skill_matches(["Python"], [])

        with (
            patch("etip_api.services.llm._get_redis", return_value=mock_redis),
            patch("litellm.acompletion", new=AsyncMock()) as mock_llm,
            patch("etip_api.services.llm.settings") as mock_settings,
        ):
            mock_settings.llm_model = "groq/llama-3.3-70b-versatile"
            mock_settings.groq_api_key = "test-key"
            mock_settings.openai_api_key = ""
            mock_settings.anthropic_api_key = ""

            from etip_api.services.llm import generate_explanation
            result = await generate_explanation(mock_project, mock_employee, skill_matches)

        assert result == "Cached explanation text."
        mock_llm.assert_not_awaited()
        mock_redis.set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_redis_get_error_falls_back_to_llm(
        self, mock_project, mock_employee, mock_redis, llm_response
    ):
        """If Redis raises on GET, we fall back to calling the LLM."""
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        skill_matches = _make_skill_matches(["Go"], [])

        with (
            patch("etip_api.services.llm._get_redis", return_value=mock_redis),
            patch("litellm.acompletion", new=AsyncMock(return_value=llm_response)),
            patch("etip_api.services.llm.settings") as mock_settings,
        ):
            mock_settings.llm_model = "groq/llama-3.3-70b-versatile"
            mock_settings.groq_api_key = "test-key"
            mock_settings.openai_api_key = ""
            mock_settings.anthropic_api_key = ""
            mock_settings.llm_explanation_cache_ttl = 86400

            from etip_api.services.llm import generate_explanation
            result = await generate_explanation(mock_project, mock_employee, skill_matches)

        assert result == "Juan es ideal para este proyecto."

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none_result_not_cached(
        self, mock_project, mock_employee, mock_redis
    ):
        """If the LLM call fails, result is None and Redis SET must not be called."""
        skill_matches = _make_skill_matches(["Go"], [])

        with (
            patch("etip_api.services.llm._get_redis", return_value=mock_redis),
            patch("litellm.acompletion", new=AsyncMock(side_effect=Exception("API error"))),
            patch("etip_api.services.llm.settings") as mock_settings,
        ):
            mock_settings.llm_model = "groq/llama-3.3-70b-versatile"
            mock_settings.groq_api_key = "test-key"
            mock_settings.openai_api_key = ""
            mock_settings.anthropic_api_key = ""
            mock_settings.llm_explanation_cache_ttl = 86400

            from etip_api.services.llm import generate_explanation
            result = await generate_explanation(mock_project, mock_employee, skill_matches)

        assert result is None
        mock_redis.set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_api_key_returns_none_skips_redis(
        self, mock_project, mock_employee, mock_redis
    ):
        """When no API key is configured the function returns None before touching Redis."""
        skill_matches = _make_skill_matches(["Python"], [])

        with (
            patch("etip_api.services.llm._get_redis", return_value=mock_redis),
            patch("etip_api.services.llm.settings") as mock_settings,
        ):
            mock_settings.llm_model = "groq/llama-3.3-70b-versatile"
            mock_settings.groq_api_key = ""           # no key → early return
            mock_settings.openai_api_key = ""
            mock_settings.anthropic_api_key = ""

            from etip_api.services.llm import generate_explanation
            result = await generate_explanation(mock_project, mock_employee, skill_matches)

        assert result is None
        mock_redis.get.assert_not_awaited()
        mock_redis.set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_ttl_uses_settings_value(
        self, mock_project, mock_employee, mock_redis, llm_response
    ):
        """The TTL passed to Redis SET must come from settings.llm_explanation_cache_ttl."""
        skill_matches = _make_skill_matches(["Python"], [])

        with (
            patch("etip_api.services.llm._get_redis", return_value=mock_redis),
            patch("litellm.acompletion", new=AsyncMock(return_value=llm_response)),
            patch("etip_api.services.llm.settings") as mock_settings,
        ):
            mock_settings.llm_model = "groq/llama-3.3-70b-versatile"
            mock_settings.groq_api_key = "test-key"
            mock_settings.openai_api_key = ""
            mock_settings.anthropic_api_key = ""
            mock_settings.llm_explanation_cache_ttl = 3600  # custom TTL

            from etip_api.services.llm import generate_explanation
            await generate_explanation(mock_project, mock_employee, skill_matches)

        _, kwargs = mock_redis.set.call_args
        assert kwargs.get("ex") == 3600

    @pytest.mark.asyncio
    async def test_cache_key_includes_both_ids(
        self, mock_project, mock_employee, mock_redis, llm_response, project_id, employee_id
    ):
        """Cache key must embed both project.id and employee.id."""
        skill_matches = _make_skill_matches(["Python"], [])
        expected_key = f"llm:explanation:{project_id}:{employee_id}"

        with (
            patch("etip_api.services.llm._get_redis", return_value=mock_redis),
            patch("litellm.acompletion", new=AsyncMock(return_value=llm_response)),
            patch("etip_api.services.llm.settings") as mock_settings,
        ):
            mock_settings.llm_model = "groq/llama-3.3-70b-versatile"
            mock_settings.groq_api_key = "test-key"
            mock_settings.openai_api_key = ""
            mock_settings.anthropic_api_key = ""
            mock_settings.llm_explanation_cache_ttl = 86400

            from etip_api.services.llm import generate_explanation
            await generate_explanation(mock_project, mock_employee, skill_matches)

        mock_redis.get.assert_awaited_once_with(expected_key)
        set_args = mock_redis.set.call_args[0]
        assert set_args[0] == expected_key

    @pytest.mark.asyncio
    async def test_redis_set_error_does_not_crash(
        self, mock_project, mock_employee, mock_redis, llm_response
    ):
        """If Redis SET fails, the function still returns the LLM result (no exception)."""
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis write failed"))
        skill_matches = _make_skill_matches(["Python"], [])

        with (
            patch("etip_api.services.llm._get_redis", return_value=mock_redis),
            patch("litellm.acompletion", new=AsyncMock(return_value=llm_response)),
            patch("etip_api.services.llm.settings") as mock_settings,
        ):
            mock_settings.llm_model = "groq/llama-3.3-70b-versatile"
            mock_settings.groq_api_key = "test-key"
            mock_settings.openai_api_key = ""
            mock_settings.anthropic_api_key = ""
            mock_settings.llm_explanation_cache_ttl = 86400

            from etip_api.services.llm import generate_explanation
            result = await generate_explanation(mock_project, mock_employee, skill_matches)

        assert result == "Juan es ideal para este proyecto."
