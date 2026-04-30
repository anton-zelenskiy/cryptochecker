from __future__ import annotations

from project.celery_app import celery_app
from project.services.orderbook_walls_service import OrderBookWallsService
from project.tasks.asyncio_runner import run as run_async


@celery_app.task(name="project.tasks.orderbook.ingest_tracked_orderbook_walls")
def ingest_tracked_orderbook_walls() -> None:
    run_async(OrderBookWallsService().ingest_tracked_orderbook_walls())
