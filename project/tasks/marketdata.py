from __future__ import annotations

from project.celery_app import celery_app
from project.services.marketdata_service import MarketDataService
from project.tasks.asyncio_runner import run as run_async


@celery_app.task(name="project.tasks.marketdata.ingest_tracked_candles")
def ingest_tracked_candles() -> None:
    run_async(MarketDataService().ingest_tracked_candles())

