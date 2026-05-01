from __future__ import annotations

from project.celery_app import celery_app
from project.core.config import settings
from project.services.marketdata_service import MarketDataService
from project.services.screener_service import ScreenerService
from project.tasks.asyncio_runner import run as run_async


async def _run_screener_v2_async() -> None:
    await MarketDataService().ingest_tracked_candles_multi()
    await ScreenerService().run_for_all_tracked_and_notify(
        run_llm_recheck=settings.SCREENER_LLM_RECHECK_ENABLED,
    )


@celery_app.task(name="project.tasks.screener.run_screener_v2")
def run_screener_v2() -> None:
    run_async(_run_screener_v2_async())
