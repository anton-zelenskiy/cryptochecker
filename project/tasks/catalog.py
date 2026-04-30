from __future__ import annotations

import structlog

from project.celery_app import celery_app
from project.services.catalog import refresh_catalog_top300_non_stablecoins
from project.tasks.asyncio_runner import run as run_async


logger = structlog.get_logger(__name__)


@celery_app.task(name="project.tasks.catalog.refresh_catalog_top300")
def refresh_catalog_top300() -> None:
    run_async(_refresh())


async def _refresh() -> None:
    try:
        await refresh_catalog_top300_non_stablecoins()
    except Exception as e:
        logger.warning("catalog celery task failed", error=str(e))
