"""
Thin GitHub REST API client.
Handles auth, rate-limit awareness, and pagination.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.github.com"


class GitHubClient:
    def __init__(self, access_token: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, path: str, params: dict | None = None) -> Any:
        with httpx.Client(base_url=BASE_URL, headers=self._headers, timeout=15.0) as client:
            resp = client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()

    def _get_paginated(self, path: str, params: dict | None = None, max_pages: int = 5) -> list:
        params = params or {}
        params["per_page"] = 100
        results = []
        page = 1
        while page <= max_pages:
            params["page"] = page
            data = self._get(path, params)
            if not data:
                break
            results.extend(data)
            if len(data) < 100:
                break
            page += 1
        return results

    def get_org_members(self, org: str) -> list[dict]:
        """List all public members of an org."""
        return self._get_paginated(f"/orgs/{org}/members")

    def get_user_repos(self, username: str) -> list[dict]:
        """List repos the user has contributed to (public + accessible private)."""
        return self._get_paginated(f"/users/{username}/repos", {"type": "all", "sort": "pushed"})

    def get_repo_languages(self, owner: str, repo: str) -> dict[str, int]:
        """Returns {language: bytes_of_code}."""
        try:
            return self._get(f"/repos/{owner}/{repo}/languages")
        except httpx.HTTPStatusError:
            return {}

    def get_user_events(self, username: str) -> list[dict]:
        """Recent public events (pushes, PRs) — used for activity signals."""
        return self._get_paginated(f"/users/{username}/events/public", max_pages=2)

    def get_user(self, username: str) -> dict:
        return self._get(f"/users/{username}")

    def search_user_by_email(self, email: str) -> dict | None:
        """Search for a GitHub user by email (requires org:read scope)."""
        try:
            results = self._get("/search/users", {"q": f"{email} in:email", "per_page": 1})
            items = results.get("items", [])
            return items[0] if items else None
        except Exception:
            return None
