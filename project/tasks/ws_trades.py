from __future__ import annotations

from project.celery_app import celery_app
from project.services.ws_trades_service import WsTradesService
from project.tasks.asyncio_runner import run as run_async


@celery_app.task(name="project.tasks.ws_trades.ingest_tracked_trades_ws")
def ingest_tracked_trades_ws() -> None:
    run_async(WsTradesService().ingest_tracked_trades_ws())

