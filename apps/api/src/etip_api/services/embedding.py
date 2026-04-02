"""
Embedding service — local OSS embeddings via fastembed.

fastembed uses ONNX runtime: runs on CPU, no GPU required, no API key needed.
The model is downloaded once on first use (~130MB for bge-small).

Default model: BAAI/bge-small-en-v1.5
  - 384 dimensions
  - Excellent quality/speed tradeoff
  - Optimised for semantic similarity

Alternative: nomic-ai/nomic-embed-text-v1.5
  - 768 dimensions, higher quality
  - Set EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5 in .env
"""

from __future__ import annotations

import logging
from functools import lru_cache

from etip_core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def _get_embedding_model():
    """Lazy-load the fastembed model (downloaded on first call)."""
    from fastembed import TextEmbedding

    logger.info("Loading embedding model: %s", settings.embedding_model)
    return TextEmbedding(model_name=settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts. Returns a list of float vectors.
    Runs locally via ONNX — no API call, no cost.
    """
    model = _get_embedding_model()
    embeddings = list(model.embed(texts))
    return [e.tolist() for e in embeddings]


def embed_one(text: str) -> list[float]:
    """Convenience wrapper for a single text."""
    return embed_texts([text])[0]


def embed_employee_profile(employee: object, skills: list[object]) -> list[float]:
    """
    Build a single embedding for an employee profile combining:
    - full_name + title + department
    - skill labels (space-separated)

    This is the vector stored in Qdrant and searched at query time.
    """
    skill_labels = " ".join(s.preferred_label for s in skills)  # type: ignore[attr-defined]
    profile_text = (
        f"{getattr(employee, 'full_name', '')} "
        f"{getattr(employee, 'title', '') or ''} "
        f"{getattr(employee, 'department', '') or ''} "
        f"{skill_labels}"
    ).strip()

    return embed_one(profile_text)


def embed_project_requirements(project: object) -> list[float]:
    """
    Build a query embedding for a project's required skills.
    Used as the search vector against employee profile embeddings in Qdrant.
    """
    required: list[dict] = getattr(project, "required_skills", []) or []
    skill_labels = " ".join(r.get("skill_label", r.get("label", "")) for r in required)
    query_text = (
        f"{getattr(project, 'name', '')} "
        f"{getattr(project, 'description', '') or ''} "
        f"{skill_labels}"
    ).strip()

    return embed_one(query_text)
