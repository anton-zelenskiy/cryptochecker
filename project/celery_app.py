from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from project.core.config import settings


celery_app = Celery("cryptochecker")
celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    task_default_queue="default",
    task_ignore_result=True,
    timezone="UTC",
    beat_schedule={
        # Ingest candles tail for tracked assets
        "ingest_candles": {
            "task": "project.tasks.marketdata.ingest_tracked_candles",
            "schedule": crontab(minute="*/1"),
        },
        # Paper trading simulation refresh
        "paper_trading_tick": {
            "task": "project.tasks.paper_trading.paper_trading_tick",
            "schedule": crontab(minute="*/1"),
        },
    },
)

