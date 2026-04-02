"""Tests for /api/v1/connectors router."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etip_api.models.connector import ConnectorConfig
from tests.conftest import TENANT_ID


def _make_connector_config(name: str = "github") -> ConnectorConfig:
    from etip_api.services.crypto import encrypt_config

    c = ConnectorConfig()
    c.id = uuid.uuid4()
    c.tenant_id = TENANT_ID
    c.connector_name = name
    c.is_active = True
    c.sync_status = "idle"
    c.last_sync_at = None
    c.config_encrypted = encrypt_config({"access_token": "tok", "org": "acme"})
    return c


class TestListConnectors:
    @pytest.mark.asyncio
    async def test_admin_can_list(self, client, as_admin, override_db):
        config = _make_connector_config("github")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [config]
        override_db.execute.return_value = mock_result

        resp = await client.get("/api/v1/connectors")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["connector_name"] == "github"

    @pytest.mark.asyncio
    async def test_list_query_scoped_to_tenant(self, client, as_admin, override_db):
        """The SELECT must include tenant_id in the WHERE clause."""
        from sqlalchemy.dialects.postgresql import dialect as pg_dialect

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        captured = {}

        async def _capture(stmt, *args, **kwargs):
            captured["stmt"] = stmt
            return mock_result

        override_db.execute = _capture

        await client.get("/api/v1/connectors")

        compiled = captured["stmt"].compile(dialect=pg_dialect())
        assert "tenant_id" in str(compiled)


class TestListAvailableConnectors:
    @pytest.mark.asyncio
    async def test_returns_installed_connectors(self, client, as_admin, override_db):
        with patch("etip_api.routers.connectors.get_connector_names", return_value=["github", "jira"]):
            resp = await client.get("/api/v1/connectors/available")

        assert resp.status_code == 200
        assert "github" in resp.json()
        assert "jira" in resp.json()


class TestCreateConnector:
    @pytest.mark.asyncio
    async def test_admin_can_create_installed_connector(self, client, as_admin, override_db):
        with patch("etip_api.routers.connectors.get_connector_names", return_value=["github"]):
            with patch("etip_api.services.audit.log_action", new=AsyncMock()):
                async def mock_refresh(obj):
                    obj.id = uuid.uuid4()
                    obj.is_active = True
                    obj.sync_status = None
                    obj.last_sync_at = None

                override_db.refresh = mock_refresh

                resp = await client.post(
                    "/api/v1/connectors",
                    json={"connector_name": "github", "config": {"access_token": "tok", "org": "acme"}},
                )

        assert resp.status_code == 201
        assert resp.json()["connector_name"] == "github"

    @pytest.mark.asyncio
    async def test_uninstalled_connector_returns_400(self, client, as_admin, override_db):
        with patch("etip_api.routers.connectors.get_connector_names", return_value=["github"]):
            resp = await client.post(
                "/api/v1/connectors",
                json={"connector_name": "salesforce", "config": {}},
            )

        assert resp.status_code == 400
        assert "not installed" in resp.json()["detail"]


class TestTriggerSync:
    @pytest.mark.asyncio
    async def test_triggers_celery_task(self, client, as_admin, override_db):
        config = _make_connector_config("github")
        override_db.get.return_value = config

        mock_task = MagicMock()
        mock_task.id = "celery-task-abc"

        with patch("etip_api.routers.connectors.sync_connector_task") as mock_celery:
            mock_celery.delay.return_value = mock_task
            with patch("etip_api.services.audit.log_action", new=AsyncMock()):
                resp = await client.post(f"/api/v1/connectors/{config.id}/sync")

        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "celery-task-abc"
        assert body["status"] == "syncing"

    @pytest.mark.asyncio
    async def test_unknown_connector_returns_404(self, client, as_admin, override_db):
        override_db.get.return_value = None
        resp = await client.post(f"/api/v1/connectors/{uuid.uuid4()}/sync")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_connector_returns_404(self, client, as_admin, override_db):
        """A connector that belongs to a different tenant must look like it doesn't exist."""
        config = _make_connector_config("github")
        config.tenant_id = uuid.uuid4()  # different tenant
        override_db.get.return_value = config

        resp = await client.post(f"/api/v1/connectors/{config.id}/sync")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sync_passes_connector_id_to_task(self, client, as_admin, override_db):
        """connector_id must be forwarded to the Celery task so it can update sync_status."""
        config = _make_connector_config("github")
        override_db.get.return_value = config

        mock_task = MagicMock()
        mock_task.id = "task-id-1"

        with patch("etip_api.routers.connectors.sync_connector_task") as mock_celery:
            mock_celery.delay.return_value = mock_task
            with patch("etip_api.services.audit.log_action", new=AsyncMock()):
                await client.post(f"/api/v1/connectors/{config.id}/sync")

        call_kwargs = mock_celery.delay.call_args.kwargs
        assert call_kwargs["connector_id"] == str(config.id)


class TestConnectorEncryption:
    @pytest.mark.asyncio
    async def test_create_stores_encrypted_envelope_not_plaintext(
        self, client, as_admin, override_db
    ):
        stored_config = {}

        from etip_api.models.connector import ConnectorConfig as CC

        def capture_add(obj):
            if isinstance(obj, CC):
                stored_config.update(obj.config_encrypted)

        override_db.add = capture_add

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.is_active = True
            obj.sync_status = None
            obj.last_sync_at = None

        override_db.refresh = mock_refresh

        with patch("etip_api.routers.connectors.get_connector_names", return_value=["github"]):
            with patch("etip_api.services.audit.log_action", new=AsyncMock()):
                resp = await client.post(
                    "/api/v1/connectors",
                    json={"connector_name": "github", "config": {"access_token": "ghp_secret"}},
                )

        assert resp.status_code == 201
        assert "access_token" not in stored_config
        assert stored_config.get("v") == 1
        assert "ct" in stored_config

    @pytest.mark.asyncio
    async def test_trigger_sync_passes_decrypted_config_to_task(
        self, client, as_admin, override_db
    ):
        from etip_api.services.crypto import encrypt_config
        from etip_api.models.connector import ConnectorConfig as CC

        config = CC()
        config.id = uuid.uuid4()
        config.tenant_id = TENANT_ID
        config.connector_name = "github"
        config.is_active = True
        config.sync_status = "idle"
        config.config_encrypted = encrypt_config({"access_token": "ghp_plaintext"})
        override_db.get.return_value = config

        mock_task = MagicMock()
        mock_task.id = "task-xyz"

        with patch("etip_api.routers.connectors.sync_connector_task") as mock_celery:
            mock_celery.delay.return_value = mock_task
            with patch("etip_api.services.audit.log_action", new=AsyncMock()):
                resp = await client.post(f"/api/v1/connectors/{config.id}/sync")

        assert resp.status_code == 200
        call_kwargs = mock_celery.delay.call_args.kwargs
        assert call_kwargs["connector_config"] == {"access_token": "ghp_plaintext"}
