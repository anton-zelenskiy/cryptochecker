from __future__ import annotations

from project.celery_app import celery_app
from project.services.trade_clusters_service import TradeClustersService
from project.tasks.asyncio_runner import run as run_async


@celery_app.task(name="project.tasks.trade_clusters.cluster_recent_large_buys")
def cluster_recent_large_buys() -> None:
    run_async(TradeClustersService().cluster_recent_large_buys())
