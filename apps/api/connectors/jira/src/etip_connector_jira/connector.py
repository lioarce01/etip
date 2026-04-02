"""
Jira Cloud connector — implements ETIP hookspecs.

Required config keys:
    base_url:  str  — https://yoursite.atlassian.net
    email:     str  — Atlassian account email
    api_token: str  — API token from id.atlassian.com/manage/api-tokens

Optional:
    project_keys: str  — comma-separated Jira project keys to limit scope (e.g. "BE,MOB")
"""

import logging
from typing import Any

from etip_connector_jira.client import JiraClient, WORK_CATEGORIES
from etip_core.hookspecs import hookimpl

logger = logging.getLogger(__name__)

# Confidence weights by status category
_CONFIDENCE = {"done": 0.8, "indeterminate": 0.6}


def _make_client(config: dict) -> JiraClient:
    return JiraClient(
        base_url=config["base_url"],
        email=config["email"],
        api_token=config["api_token"],
    )


def _parse_project_keys(config: dict) -> list[str] | None:
    raw = config.get("project_keys", "").strip()
    if not raw:
        return None
    return [k.strip() for k in raw.split(",") if k.strip()]


class JiraConnector:

    @hookimpl
    def get_connector_name(self) -> str:
        return "jira"

    @hookimpl
    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "base_url":     {"type": "string", "description": "Jira Cloud URL (https://yoursite.atlassian.net)"},
                "email":        {"type": "string", "description": "Atlassian account email"},
                "api_token":    {"type": "string", "description": "API token from id.atlassian.com/manage/api-tokens"},
                "project_keys": {"type": "string", "description": "Optional: comma-separated project keys to limit scope"},
            },
            "required": ["base_url", "email", "api_token"],
        }

    @hookimpl
    def health_check(self, config: dict) -> dict:
        try:
            client = _make_client(config)
            me = client.get_myself()
            if not me.get("active"):
                return {"ok": False, "detail": "Jira user is inactive"}
            return {"ok": True, "detail": f"Connected as {me.get('displayName')} ({me.get('emailAddress')})"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}

    @hookimpl
    def sync_employees(self, tenant_id: str, config: dict) -> list[dict]:
        """
        Returns active human Jira users as EmployeeDTO-compatible dicts.
        Filters out app/bot accounts and users without a visible email address.
        """
        client = _make_client(config)
        try:
            users = client.get_users()
        except Exception:
            logger.exception("Jira: failed to fetch users")
            return []

        employees = []
        for user in users:
            employees.append({
                "external_id":   user["accountId"],
                "email":         user["emailAddress"],
                "full_name":     user.get("displayName") or user["emailAddress"],
                "title":         None,
                "department":    None,
                "manager_email": None,
                "source":        "jira",
                "raw":           user,
            })

        logger.info("Jira: synced %d employees", len(employees))
        return employees

    @hookimpl
    def sync_skills(self, tenant_id: str, employee_external_id: str, config: dict) -> list[dict]:
        """
        Infers skills for one employee (Jira accountId) from their assigned issues.
        Skill signals come from issue labels and components on done/in-progress issues.
        Confidence: done=0.8, in-progress=0.6.
        """
        client = _make_client(config)

        jql = (
            f'assignee = "{employee_external_id}" '
            'AND statusCategory in ("In Progress", "Done") '
            "ORDER BY updated DESC"
        )
        try:
            issues = client.search_issues(jql, max_issues=200)
        except Exception:
            logger.warning("Jira: failed to fetch issues for accountId=%s", employee_external_id)
            return []

        # Count label/component occurrences per status category
        from collections import defaultdict
        signal: dict[str, dict] = defaultdict(lambda: {"done_count": 0, "inprogress_count": 0})

        for issue in issues:
            f = issue.get("fields", {})
            cat_key = f.get("status", {}).get("statusCategory", {}).get("key", "")
            labels = [lb.lower() for lb in f.get("labels", []) if lb]
            comps  = [c["name"].lower() for c in f.get("components", []) if c.get("name")]

            for term in labels + comps:
                if cat_key == "done":
                    signal[term]["done_count"] += 1
                elif cat_key == "indeterminate":
                    signal[term]["inprogress_count"] += 1

        skills = []
        for label, counts in signal.items():
            # Confidence: weight done higher than in-progress
            base = (counts["done_count"] * 0.8 + counts["inprogress_count"] * 0.6)
            confidence = min(base / 5.0, 1.0)  # saturate at 5 occurrences
            if confidence < 0.1:
                continue
            skills.append({
                "raw_label":        label,
                "esco_uri":         None,
                "nivel":            None,
                "confidence_score": round(confidence, 3),
                "source":           "jira",
                "evidence": {
                    "done_count":       counts["done_count"],
                    "inprogress_count": counts["inprogress_count"],
                },
            })

        logger.info("Jira: inferred %d skills for accountId=%s", len(skills), employee_external_id)
        return skills

    @hookimpl
    def sync_projects(self, tenant_id: str, config: dict) -> list[dict]:
        """
        Imports Jira Projects as ETIP projects.
        Required skills are inferred from the most frequent labels/components
        across done/in-progress issues in each project.
        Jira projects have no start/end dates — those fields will be None.
        """
        client = _make_client(config)
        project_keys = _parse_project_keys(config)

        try:
            jira_projects = client.get_projects(project_keys=project_keys)
        except Exception:
            logger.exception("Jira: failed to fetch projects")
            return []

        projects = []
        for jp in jira_projects:
            key = jp.get("key", "")
            name = jp.get("name", key)
            description = jp.get("description") or None

            top_labels = client.get_top_labels_for_project(key)
            required_skills = [
                {"skill_label": label, "esco_uri": None, "level": None, "weight": 1.0}
                for label in top_labels
            ]

            projects.append({
                "external_id": key,
                "name":        name,
                "description": description,
                "source":      "jira",
                "raw": {
                    "jira_project_key": key,
                    "jira_project_type": jp.get("projectTypeKey"),
                    "required_skills":  required_skills,
                },
            })

        logger.info("Jira: synced %d projects", len(projects))
        return projects
