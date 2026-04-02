"""
GitHub connector — implements ETIP hookspecs.

Required config keys:
    access_token: str   — GitHub PAT with repo + read:org scopes
    org: str            — GitHub organisation slug (e.g. "my-company")

Optional:
    max_repos_per_user: int  — cap repos analysed per employee (default 20)
"""

import logging
from typing import Any

from etip_connector_github.client import GitHubClient
from etip_connector_github.skills import infer_skills_from_repos
from etip_core.hookspecs import hookimpl

logger = logging.getLogger(__name__)


class GitHubConnector:

    @hookimpl
    def get_connector_name(self) -> str:
        return "github"

    @hookimpl
    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "access_token": {"type": "string", "description": "GitHub PAT (repo + read:org)"},
                "org": {"type": "string", "description": "GitHub organisation slug"},
                "max_repos_per_user": {"type": "integer", "default": 20},
            },
            "required": ["access_token", "org"],
        }

    @hookimpl
    def sync_employees(self, tenant_id: str, config: dict) -> list[dict]:
        """
        Returns org members as EmployeeDTO-compatible dicts.
        Note: GitHub profiles have limited HR data; email may be empty for private profiles.
        """
        client = GitHubClient(config["access_token"])
        org = config["org"]

        try:
            members = client.get_org_members(org)
        except Exception:
            logger.exception("Failed to fetch org members for %s", org)
            return []

        employees = []
        for member in members:
            username = member.get("login", "")
            try:
                user_detail = client.get_user(username)
            except Exception:
                logger.warning("Could not fetch details for GitHub user %s", username)
                continue

            email = user_detail.get("email") or f"{username}@github-noemail.invalid"
            full_name = user_detail.get("name") or username

            employees.append({
                "external_id": username,
                "email": email,
                "full_name": full_name,
                "title": None,
                "department": None,
                "manager_email": None,
                "source": "github",
                "raw": user_detail,
            })

        logger.info("GitHub: synced %d employees for org=%s", len(employees), org)
        return employees

    @hookimpl
    def sync_skills(
        self,
        tenant_id: str,
        employee_external_id: str,
        config: dict,
    ) -> list[dict]:
        """
        Infers skills for a single employee (GitHub username) from their repos.
        """
        client = GitHubClient(config["access_token"])
        max_repos = config.get("max_repos_per_user", 20)

        try:
            repos = client.get_user_repos(employee_external_id)[:max_repos]
        except Exception:
            logger.warning("Could not fetch repos for GitHub user %s", employee_external_id)
            return []

        # Fetch language breakdown per repo
        languages_per_repo: dict[str, dict] = {}
        for repo in repos:
            full_name = repo.get("full_name", "")
            owner, name = full_name.split("/", 1) if "/" in full_name else ("", full_name)
            languages_per_repo[full_name] = client.get_repo_languages(owner, name)

        skills = infer_skills_from_repos(repos, languages_per_repo)
        logger.info(
            "GitHub: inferred %d skills for user=%s",
            len(skills),
            employee_external_id,
        )
        return skills

    @hookimpl
    def sync_projects(self, tenant_id: str, config: dict) -> list[dict]:
        # GitHub repos can be treated as projects in v1; skipped for MVP
        return []

    @hookimpl
    def health_check(self, config: dict) -> dict:
        try:
            client = GitHubClient(config["access_token"])
            client._get("/user")
            return {"ok": True, "detail": "GitHub API reachable"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}
