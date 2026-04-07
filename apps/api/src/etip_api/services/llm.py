"""
LLM service — generates human-readable match explanations via LiteLLM.

LiteLLM provides a unified interface for 100+ providers. Switch providers
by changing LLM_MODEL in .env — no code changes required:

    LLM_MODEL=gpt-4o-mini                    → OpenAI
    LLM_MODEL=claude-haiku-4-5-20251001      → Anthropic
    LLM_MODEL=groq/llama-3.3-70b-versatile   → Groq (free tier)
    LLM_MODEL=ollama/llama3.2                → Local Ollama

Explanations are cached in Redis (TTL: llm_explanation_cache_ttl seconds,
default 24h). Falls back to calling the LLM directly if Redis is unavailable.
"""

from __future__ import annotations

import logging
import os

import redis.asyncio as aioredis

from etip_core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Set provider API keys as env vars — LiteLLM picks them up automatically
if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
if settings.anthropic_api_key:
    os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
if settings.groq_api_key:
    os.environ["GROQ_API_KEY"] = settings.groq_api_key

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis | None:
    """Lazy-init Redis client. Returns None and logs a warning if unavailable."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            logger.warning("Redis unavailable — LLM explanation caching disabled")
    return _redis_client


def _has_key_for_model(model: str) -> bool:
    """Return False if the model's provider requires an API key that isn't set."""
    if model.startswith("groq/") and not settings.groq_api_key:
        return False
    if model.startswith(("gpt-", "o1", "openai/")) and not settings.openai_api_key:
        return False
    if model.startswith(("claude-", "anthropic/")) and not settings.anthropic_api_key:
        return False
    return True


async def generate_explanation(project: object, employee: object, skill_matches: list) -> str | None:
    """Generate a 2-3 sentence match explanation in Spanish for the TM.

    Results are cached in Redis keyed by (project.id, employee.id) to avoid
    redundant LLM calls on re-runs of the same matching pipeline.
    """
    if not settings.llm_model or not _has_key_for_model(settings.llm_model):
        return None

    cache_key = f"llm:explanation:{project.id}:{employee.id}"  # type: ignore[attr-defined]
    redis = _get_redis()

    # Cache read
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            logger.warning("Redis GET failed for key=%s — proceeding without cache", cache_key)

    # LLM call
    try:
        import litellm

        matched = [s.skill_label for s in skill_matches if s.matched]
        missing = [s.skill_label for s in skill_matches if not s.matched]

        prompt = (
            f"Proyecto: {project.name}\n"  # type: ignore[attr-defined]
            f"Descripción: {project.description or 'N/A'}\n"
            f"Skills requeridas: {', '.join(s.skill_label for s in skill_matches)}\n\n"
            f"Candidato: {employee.full_name}\n"  # type: ignore[attr-defined]
            f"Título: {employee.title or 'N/A'}\n"  # type: ignore[attr-defined]
            f"Skills que coinciden: {', '.join(matched) or 'ninguna'}\n"
            f"Skills faltantes: {', '.join(missing) or 'ninguna'}\n\n"
            "En 2-3 oraciones en español, explica por qué este candidato es (o no es) "
            "adecuado para el proyecto. Sé conciso y técnico."
        )

        response = await litellm.acompletion(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un asistente experto en asignación de talento técnico.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
            temperature=0.3,
        )
        result: str | None = response.choices[0].message.content

    except Exception:
        logger.exception("LLM explanation failed for model=%s — returning None", settings.llm_model)
        result = None

    # Cache write (only on success)
    if result and redis:
        try:
            await redis.set(cache_key, result, ex=settings.llm_explanation_cache_ttl)
        except Exception:
            logger.warning("Redis SET failed for key=%s — result not cached", cache_key)

    return result
