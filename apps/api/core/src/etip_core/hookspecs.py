"""
ETIP plugin hookspecs.

Every connector package must implement the relevant hooks using @hookimpl.
The PluginManager fans out calls to all registered connectors and merges results.

Usage in a connector:
    from etip_core import hookimpl

    class MyConnector:
        @hookimpl
        def get_connector_name(self) -> str:
            return "my-connector"

        @hookimpl
        def sync_employees(self, tenant_id: str, config: dict) -> list[dict]:
            ...
"""

import pluggy

PROJECT_NAME = "etip"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class ETIPSpec:
    @hookspec
    def get_connector_name(self) -> str:
        """Return the unique slug for this connector, e.g. 'github', 'jira'."""

    @hookspec
    def get_config_schema(self) -> dict:
        """
        Return a JSON Schema dict describing the configuration fields
        required by this connector (stored encrypted in connector_configs).
        """

    @hookspec
    def sync_employees(self, tenant_id: str, config: dict) -> list[dict]:
        """
        Fetch/sync employees from the external source.

        Returns a list of dicts conforming to EmployeeDTO fields:
            id, email, full_name, title, department, manager_email,
            external_id, source
        """

    @hookspec
    def sync_skills(
        self,
        tenant_id: str,
        employee_external_id: str,
        config: dict,
    ) -> list[dict]:
        """
        Infer/extract skills for a single employee from the external source.

        Returns a list of dicts conforming to SkillDTO fields:
            raw_label, esco_uri, nivel, confidence_score, source, evidence
        """

    @hookspec
    def sync_projects(self, tenant_id: str, config: dict) -> list[dict]:
        """
        Sync projects/issues from the external source (e.g. Jira epics).

        Returns a list of dicts conforming to ProjectDTO fields:
            external_id, name, description, source
        """

    @hookspec
    def health_check(self, config: dict) -> dict:
        """
        Verify the connector can reach the external service with the given config.
        Returns {"ok": bool, "detail": str}
        """
