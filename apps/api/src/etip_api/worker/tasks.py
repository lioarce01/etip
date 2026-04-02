"""
Celery tasks for connector sync jobs.
Each task is dispatched by POST /connectors/{id}/sync and runs in the background.
"""

import logging
from datetime import UTC, datetime

from celery import shared_task

from etip_api.worker.celery_app import celery_app
from etip_core.plugin_manager import pm

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="etip.sync_connector", max_retries=3, default_retry_delay=60)
def sync_connector_task(
    self,
    tenant_id: str,
    connector_name: str,
    connector_config: dict,
    connector_id: str | None = None,
) -> dict:
    """
    Sync a single connector for a tenant.
    Calls hookspecs: sync_employees → sync_skills → sync_projects
    """
    from etip_api.worker.sync import run_sync

    try:
        result = run_sync(
            tenant_id=tenant_id,
            connector_name=connector_name,
            config=connector_config,
            connector_id=connector_id,
        )
        return result
    except Exception as exc:
        logger.exception("Sync failed for connector=%s tenant=%s", connector_name, tenant_id)
        raise self.retry(exc=exc)
