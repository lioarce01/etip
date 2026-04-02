"""
LLM service — generates human-readable match explanations via LiteLLM.

LiteLLM provides a unified interface for 100+ providers. Switch providers
by changing LLM_MODEL in .env — no code changes required:

    LLM_MODEL=gpt-4o-mini                    → OpenAI
    LLM_MODEL=claude-haiku-4-5-20251001      → Anthropic
    LLM_MODEL=groq/llama-3.3-70b-versatile   → Groq (free tier)
    LLM_MODEL=ollama/llama3.2                → Local Ollama
"""

from __future__ import annotations

import logging
import os

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
    """Generate a 2-3 sentence match explanation in Spanish for the TM."""
    if not settings.llm_model or not _has_key_for_model(settings.llm_model):
        return None

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
        return response.choices[0].message.content

    except Exception:
        logger.exception("LLM explanation failed for model=%s — returning None", settings.llm_model)
        return None
