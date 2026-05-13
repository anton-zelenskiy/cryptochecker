from __future__ import annotations

from project.celery_app import celery_app
from project.services.volatility_service import VolatilityService
from project.tasks.asyncio_runner import run as run_async


@celery_app.task(name="project.tasks.volatility.detect_big_moves")
def detect_big_moves() -> None:
    service = VolatilityService()
    run_async(service.run_all_volatility_checks())

