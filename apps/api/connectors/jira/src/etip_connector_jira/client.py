"""
Jira Cloud REST API v3 client.
Auth: Basic (email:api_token base64-encoded).
Pagination: startAt + maxResults + isLast boolean.
"""

import base64
import logging
from collections import Counter
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Only these status categories carry evidence of real work
WORK_CATEGORIES = ("indeterminate", "done")


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ── Low-level ─────────────────────────────────────────────────────────────

    def _get(self, path: str, **params: Any) -> Any:
        url = f"{self._base_url}{path}"
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers=self._headers, params=params)
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, body: dict) -> Any:
        url = f"{self._base_url}{path}"
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=self._headers, json=body)
            resp.raise_for_status()
            return resp.json()

    def _get_paginated(self, path: str, result_key: str = "values", max_pages: int = 20, **params: Any) -> list[dict]:
        """Generic startAt/isLast paginator for Jira REST v3."""
        results: list[dict] = []
        start_at = 0
        max_results = params.pop("maxResults", 50)

        for _ in range(max_pages):
            data = self._get(path, startAt=start_at, maxResults=max_results, **params)
            # Users endpoint returns a plain list; project/search returns {values:[]}
            if isinstance(data, list):
                page = data
                is_last = len(page) < max_results
            else:
                page = data.get(result_key, [])
                is_last = data.get("isLast", True)

            results.extend(page)
            if is_last or not page:
                break
            start_at += len(page)

        return results

    # ── Public API ────────────────────────────────────────────────────────────

    def get_myself(self) -> dict:
        """Returns the authenticated user. Used for health check."""
        return self._get("/rest/api/3/myself")

    def get_users(self) -> list[dict]:
        """
        Returns all active human (accountType=atlassian) users that have a
        visible email address. App/bot accounts are filtered out client-side
        because Jira ignores the accountType query parameter.
        """
        all_users = self._get_paginated("/rest/api/3/users/search", result_key="values", maxResults=50)
        return [
            u for u in all_users
            if u.get("accountType") == "atlassian"
            and u.get("active")
            and u.get("emailAddress")
        ]

    def get_projects(self, project_keys: list[str] | None = None) -> list[dict]:
        """Returns all software projects, optionally filtered by key list."""
        projects = self._get_paginated(
            "/rest/api/3/project/search",
            result_key="values",
            maxResults=50,
        )
        if project_keys:
            keys = {k.strip().upper() for k in project_keys}
            projects = [p for p in projects if p.get("key", "").upper() in keys]
        return projects

    def search_issues(self, jql: str, fields: list[str] | None = None, max_issues: int = 200) -> list[dict]:
        """
        JQL issue search with cursor pagination (isLast-based).
        Returns a flat list of issue dicts.
        """
        fields = fields or ["summary", "status", "components", "labels", "issuetype", "project", "updated"]
        issues: list[dict] = []
        start_at = 0
        page_size = 50

        while len(issues) < max_issues:
            body = {
                "jql": jql,
                "fields": fields,
                "maxResults": min(page_size, max_issues - len(issues)),
                "startAt": start_at,
            }
            data = self._post("/rest/api/3/search/jql", body)
            page = data.get("issues", [])
            issues.extend(page)
            if data.get("isLast", True) or not page:
                break
            start_at += len(page)

        return issues

    def get_top_labels_for_project(self, project_key: str, top_n: int = 10) -> list[str]:
        """
        Returns the most frequently used labels across done/in-progress issues
        in a project. Used to infer required_skills for the ETIP project.
        """
        try:
            jql = (
                f'project = "{project_key}" '
                'AND statusCategory in ("In Progress", "Done") '
                "ORDER BY updated DESC"
            )
            issues = self.search_issues(jql, fields=["labels", "components"], max_issues=100)
        except Exception:
            logger.warning("Could not fetch labels for project %s", project_key)
            return []

        counter: Counter = Counter()
        for issue in issues:
            f = issue.get("fields", {})
            for label in f.get("labels", []):
                if label:
                    counter[label.lower()] += 1
            for comp in f.get("components", []):
                name = comp.get("name", "")
                if name:
                    counter[name.lower()] += 1

        return [label for label, _ in counter.most_common(top_n)]
