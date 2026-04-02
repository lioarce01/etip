"""Tests for etip_connector_github.connector — hookspec implementations."""

from unittest.mock import MagicMock, patch

import pytest

from etip_connector_github.connector import GitHubConnector


CONFIG = {"access_token": "ghp_test123", "org": "acme-corp", "max_repos_per_user": 5}
TENANT_ID = "tenant-abc"


@pytest.fixture
def connector() -> GitHubConnector:
    return GitHubConnector()


class TestGetConnectorName:
    def test_returns_github(self, connector):
        assert connector.get_connector_name() == "github"


class TestGetConfigSchema:
    def test_returns_json_schema_dict(self, connector):
        schema = connector.get_config_schema()
        assert schema["type"] == "object"
        assert "access_token" in schema["properties"]
        assert "org" in schema["properties"]
        assert "access_token" in schema["required"]

    def test_org_is_required(self, connector):
        schema = connector.get_config_schema()
        assert "org" in schema["required"]


class TestSyncEmployees:
    def test_returns_list_of_employee_dicts(self, connector):
        mock_client = MagicMock()
        mock_client.get_org_members.return_value = [{"login": "juanp"}]
        mock_client.get_user.return_value = {
            "login": "juanp",
            "name": "Juan Pérez",
            "email": "juan@acme.com",
        }

        with patch("etip_connector_github.connector.GitHubClient", return_value=mock_client):
            result = connector.sync_employees(tenant_id=TENANT_ID, config=CONFIG)

        assert len(result) == 1
        emp = result[0]
        assert emp["external_id"] == "juanp"
        assert emp["email"] == "juan@acme.com"
        assert emp["source"] == "github"

    def test_no_email_uses_fallback(self, connector):
        mock_client = MagicMock()
        mock_client.get_org_members.return_value = [{"login": "ghost"}]
        mock_client.get_user.return_value = {"login": "ghost", "name": "Ghost", "email": None}

        with patch("etip_connector_github.connector.GitHubClient", return_value=mock_client):
            result = connector.sync_employees(tenant_id=TENANT_ID, config=CONFIG)

        assert "github-noemail" in result[0]["email"]

    def test_api_error_returns_empty_list(self, connector):
        mock_client = MagicMock()
        mock_client.get_org_members.side_effect = Exception("API down")

        with patch("etip_connector_github.connector.GitHubClient", return_value=mock_client):
            result = connector.sync_employees(tenant_id=TENANT_ID, config=CONFIG)

        assert result == []

    def test_user_detail_error_skips_member(self, connector):
        mock_client = MagicMock()
        mock_client.get_org_members.return_value = [{"login": "ok"}, {"login": "bad"}]
        mock_client.get_user.side_effect = [
            {"login": "ok", "name": "OK User", "email": "ok@acme.com"},
            Exception("not found"),
        ]

        with patch("etip_connector_github.connector.GitHubClient", return_value=mock_client):
            result = connector.sync_employees(tenant_id=TENANT_ID, config=CONFIG)

        assert len(result) == 1
        assert result[0]["external_id"] == "ok"


class TestSyncSkills:
    def test_returns_skill_list(self, connector):
        mock_client = MagicMock()
        mock_client.get_user_repos.return_value = [
            {"full_name": "acme/api", "topics": ["docker"]}
        ]
        mock_client.get_repo_languages.return_value = {"Python": 80000, "SQL": 20000}

        with patch("etip_connector_github.connector.GitHubClient", return_value=mock_client):
            result = connector.sync_skills(
                tenant_id=TENANT_ID,
                employee_external_id="juanp",
                config=CONFIG,
            )

        raw_labels = [s["raw_label"] for s in result]
        assert "Python" in raw_labels
        assert "SQL" in raw_labels

    def test_respects_max_repos_limit(self, connector):
        repos = [{"full_name": f"acme/repo{i}", "topics": []} for i in range(20)]
        mock_client = MagicMock()
        mock_client.get_user_repos.return_value = repos
        mock_client.get_repo_languages.return_value = {"Python": 1000}

        config = {**CONFIG, "max_repos_per_user": 3}
        with patch("etip_connector_github.connector.GitHubClient", return_value=mock_client):
            connector.sync_skills(tenant_id=TENANT_ID, employee_external_id="u", config=config)

        # get_repo_languages should only be called 3 times
        assert mock_client.get_repo_languages.call_count == 3

    def test_repo_error_returns_empty_list(self, connector):
        mock_client = MagicMock()
        mock_client.get_user_repos.side_effect = Exception("403 Forbidden")

        with patch("etip_connector_github.connector.GitHubClient", return_value=mock_client):
            result = connector.sync_skills(
                tenant_id=TENANT_ID, employee_external_id="u", config=CONFIG
            )

        assert result == []


class TestSyncProjects:
    def test_returns_empty_list_for_mvp(self, connector):
        result = connector.sync_projects(tenant_id=TENANT_ID, config=CONFIG)
        assert result == []


class TestHealthCheck:
    def test_healthy_returns_ok_true(self, connector):
        mock_client = MagicMock()
        mock_client._get.return_value = {"login": "app"}

        with patch("etip_connector_github.connector.GitHubClient", return_value=mock_client):
            result = connector.health_check(config=CONFIG)

        assert result["ok"] is True

    def test_api_error_returns_ok_false(self, connector):
        mock_client = MagicMock()
        mock_client._get.side_effect = Exception("unauthorized")

        with patch("etip_connector_github.connector.GitHubClient", return_value=mock_client):
            result = connector.health_check(config=CONFIG)

        assert result["ok"] is False
        assert "unauthorized" in result["detail"]
