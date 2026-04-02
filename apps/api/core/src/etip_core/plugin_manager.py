"""
Singleton PluginManager — loads all registered etip connectors at startup.

Connectors installed as packages declare themselves via entry_points:
    [project.entry-points."etip"]
    github = "etip_connector_github:GitHubConnector"

Usage:
    from etip_core.plugin_manager import pm
    results = pm.hook.sync_employees(tenant_id="...", config={})
"""

import pluggy

from etip_core.hookspecs import ETIPSpec, PROJECT_NAME

pm = pluggy.PluginManager(PROJECT_NAME)
pm.add_hookspecs(ETIPSpec)


def load_connectors() -> None:
    """Discover and register all installed connector plugins."""
    from importlib.metadata import entry_points
    for ep in entry_points(group=PROJECT_NAME):
        cls = ep.load()
        pm.register(cls())


def register_connector(connector: object) -> None:
    """Manually register a connector instance (useful in tests)."""
    pm.register(connector)


def get_connector_names() -> list[str]:
    """Return the slugs of all registered connectors (deduplicated, order preserved)."""
    results = pm.hook.get_connector_name()
    seen: set[str] = set()
    out: list[str] = []
    for r in results:
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out
