"""Tests for etip_core.plugin_manager — connector registration and dispatch."""

import pytest
import pluggy

from etip_core.hookspecs import ETIPSpec, hookimpl, PROJECT_NAME
from etip_core.plugin_manager import get_connector_names, register_connector, pm


class _DummyConnector:
    """A minimal connector that implements just the name hookspec."""

    @hookimpl
    def get_connector_name(self) -> str:
        return "dummy"

    @hookimpl
    def get_config_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    @hookimpl
    def sync_employees(self, tenant_id: str, config: dict) -> list[dict]:
        return [{"external_id": "1", "email": "a@b.com", "full_name": "A", "source": "dummy"}]

    @hookimpl
    def sync_skills(self, tenant_id: str, employee_external_id: str, config: dict) -> list[dict]:
        return [{"raw_label": "Python", "source": "dummy", "confidence_score": 0.8}]

    @hookimpl
    def sync_projects(self, tenant_id: str, config: dict) -> list[dict]:
        return []

    @hookimpl
    def health_check(self, config: dict) -> dict:
        return {"ok": True, "detail": "healthy"}


@pytest.fixture
def isolated_pm():
    """A fresh PluginManager so tests don't pollute the global instance."""
    fresh = pluggy.PluginManager(PROJECT_NAME)
    fresh.add_hookspecs(ETIPSpec)
    return fresh


class TestPluginManager:
    def test_register_and_get_name(self, isolated_pm):
        connector = _DummyConnector()
        isolated_pm.register(connector)
        names = isolated_pm.hook.get_connector_name()
        assert "dummy" in names

    def test_sync_employees_returns_list(self, isolated_pm):
        isolated_pm.register(_DummyConnector())
        results = isolated_pm.hook.sync_employees(tenant_id="t1", config={})
        # pluggy returns list of results from each hookimpl
        flat = [item for batch in results for item in batch]
        assert flat[0]["email"] == "a@b.com"

    def test_sync_skills_returns_skills(self, isolated_pm):
        isolated_pm.register(_DummyConnector())
        results = isolated_pm.hook.sync_skills(
            tenant_id="t1", employee_external_id="user1", config={}
        )
        flat = [item for batch in results for item in batch]
        assert flat[0]["raw_label"] == "Python"

    def test_health_check(self, isolated_pm):
        isolated_pm.register(_DummyConnector())
        results = isolated_pm.hook.health_check(config={})
        assert any(r.get("ok") for r in results)

    def test_multiple_connectors_aggregate(self, isolated_pm):
        class _AnotherConnector:
            @hookimpl
            def get_connector_name(self) -> str:
                return "another"

            @hookimpl
            def sync_employees(self, tenant_id, config):
                return [{"external_id": "2", "email": "b@c.com", "full_name": "B", "source": "another"}]

        isolated_pm.register(_DummyConnector())
        isolated_pm.register(_AnotherConnector())
        names = isolated_pm.hook.get_connector_name()
        assert set(names) == {"dummy", "another"}

    def test_get_config_schema(self, isolated_pm):
        isolated_pm.register(_DummyConnector())
        schemas = isolated_pm.hook.get_config_schema()
        assert any(isinstance(s, dict) for s in schemas)
