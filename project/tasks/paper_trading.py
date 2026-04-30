from __future__ import annotations

from project.celery_app import celery_app
from project.services.paper_trading_service import PaperTradingService
from project.tasks.asyncio_runner import run as run_async


@celery_app.task(name="project.tasks.paper_trading.paper_trading_tick")
def paper_trading_tick() -> None:
    run_async(PaperTradingService().paper_trading_tick())

