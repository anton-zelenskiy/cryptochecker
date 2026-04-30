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
        # CoinGecko top catalog (plan §1): refresh a few times per day, staggered from ingest
        "refresh_catalog_top300": {
            "task": "project.tasks.catalog.refresh_catalog_top300",
            "schedule": crontab(minute=20, hour="*/6"),
        },
        # Coin metadata (plan §1): nightly batch for platforms/contracts (best-effort)
        "refresh_coin_metadata_platforms": {
            "task": "project.tasks.coin_metadata.refresh_coin_metadata_platforms",
            "schedule": crontab(minute=15, hour=3),
        },
        # WS trades-only slice: short periodic collector into `market_trades`
        "ingest_tracked_trades_ws": {
            "task": "project.tasks.ws_trades.ingest_tracked_trades_ws",
            "schedule": crontab(minute="*/1"),
        },
        # Volatility checker v2: react only to big moves
        "detect_big_moves": {
            "task": "project.tasks.volatility.detect_big_moves",
            "schedule": crontab(minute="*/1"),
        },
        # WS orderbook (L2) probe: detect support-side walls from first snapshots
        "ingest_tracked_orderbook_walls": {
            "task": "project.tasks.orderbook.ingest_tracked_orderbook_walls",
            "schedule": crontab(minute="*/2"),
        },
        # Large buy clustering over recent WS trades
        "cluster_recent_large_buys": {
            "task": "project.tasks.trade_clusters.cluster_recent_large_buys",
            "schedule": crontab(minute="*/1"),
        },
    },
)

import project.tasks.catalog  # noqa: E402, F401
import project.tasks.coin_metadata  # noqa: E402, F401
import project.tasks.marketdata  # noqa: E402, F401
import project.tasks.paper_trading  # noqa: E402, F401
import project.tasks.ws_trades  # noqa: E402, F401
import project.tasks.volatility  # noqa: E402, F401
import project.tasks.orderbook  # noqa: E402, F401
import project.tasks.trade_clusters  # noqa: E402, F401

