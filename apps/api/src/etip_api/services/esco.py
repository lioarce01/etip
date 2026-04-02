"""
ESCO skill normalization.
For MVP: calls the ESCO REST API. For production, swap for a local dataset lookup.
"""

import logging

import httpx

from etip_core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Simple in-process cache to avoid redundant API calls during a sync run
_cache: dict[str, dict | None] = {}


def normalize_skill(raw_label: str) -> dict | None:
    """
    Maps a raw skill string to its ESCO canonical entry.
    Returns {"uri": "...", "preferred_label": "..."} or None if not found.
    """
    key = raw_label.lower().strip()
    if key in _cache:
        return _cache[key]

    try:
        resp = httpx.get(
            f"{settings.esco_api_url}/search",
            params={"text": key, "type": "skill", "language": "en", "limit": 1},
            timeout=5.0,
        )
        resp.raise_for_status()
        results = resp.json().get("_embedded", {}).get("results", [])
        if results:
            hit = results[0]
            entry = {"uri": hit["uri"], "preferred_label": hit["title"]}
            _cache[key] = entry
            return entry
    except Exception:
        logger.debug("ESCO lookup failed for '%s' — using raw label", raw_label)

    _cache[key] = None
    return None
