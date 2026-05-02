from __future__ import annotations

import structlog

from project.celery_app import celery_app
from project.services.fundamentals_snapshot_service import refresh_tracked_fundamentals_snapshots
from project.tasks.asyncio_runner import run as run_async


logger = structlog.get_logger(__name__)


async def _refresh_tracked_async() -> None:
    n = await refresh_tracked_fundamentals_snapshots()
    logger.info("fundamentals snapshots refreshed", markets_refreshed=n)


@celery_app.task(name="project.tasks.fundamentals.refresh_tracked_fundamentals_snapshots")
def refresh_tracked_fundamentals_snapshots_task() -> None:
    run_async(_refresh_tracked_async())
