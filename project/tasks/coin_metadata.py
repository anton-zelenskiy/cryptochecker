from __future__ import annotations

import structlog

from project.celery_app import celery_app
from project.services.coin_metadata import refresh_coin_metadata_platforms_from_catalog
from project.tasks.asyncio_runner import run as run_async


logger = structlog.get_logger(__name__)


@celery_app.task(name="project.tasks.coin_metadata.refresh_coin_metadata_platforms")
def refresh_coin_metadata_platforms() -> None:
    run_async(_refresh())


async def _refresh() -> None:
    try:
        await refresh_coin_metadata_platforms_from_catalog(limit=300)
    except Exception as e:
        logger.warning("coin metadata celery task failed", error=str(e))

