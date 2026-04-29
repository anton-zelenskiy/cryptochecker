from __future__ import annotations

import datetime as dt

import structlog
from sqlalchemy import insert

from project.celery_app import celery_app
from project.core.db_session import sessionmanager
from project.marketdata.dto import NormalizedMarket
from project.marketdata.providers.bybit_candles import BybitCandleProvider
from project.marketdata.providers.kucoin_candles import KuCoinCandleProvider
from project.models.candles import Candle
from project.repositories.users import TelegramUserRepository, UserTrackedAssetRepository


logger = structlog.get_logger(__name__)


@celery_app.task(name="project.tasks.marketdata.ingest_tracked_candles")
def ingest_tracked_candles() -> None:
    """
    Periodic ingest for tracked assets.

    Runs in Celery (sync entrypoint). Internally uses async DB session via asyncio.
    """
    import asyncio

    asyncio.run(_ingest_tracked_candles())


async def _ingest_tracked_candles() -> None:
    # Best-effort: load all tracked assets across all users and ingest last ~3h of 5m candles.
    user_repo = TelegramUserRepository()
    tracked_repo = UserTrackedAssetRepository()

    # naive: list all users then assets (optimize later)
    users = await user_repo.get_all()
    markets: set[tuple[str, str]] = set()
    for u in users:
        assets = await tracked_repo.list_enabled_assets(u.id)
        for a in assets:
            markets.add((a.base_asset, a.quote_asset))

    if not markets:
        return

    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(hours=3)

    providers = [KuCoinCandleProvider(), BybitCandleProvider()]

    rows: list[dict] = []
    for base, quote in sorted(markets):
        market = NormalizedMarket(base_asset=base, quote_asset=quote)
        for p in providers:
            try:
                candles = await p.fetch_ohlcv(market, "5m", start, end)
            except Exception as e:
                logger.warning("candle fetch failed", source=p.source, market=market, error=str(e))
                continue
            for c in candles:
                rows.append(
                    {
                        "source": c.source,
                        "base_asset": c.market.base_asset,
                        "quote_asset": c.market.quote_asset,
                        "timeframe": c.timeframe,
                        "open_time_utc": c.open_time_utc,
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "close": c.close,
                        "volume_base": c.volume_base,
                        "volume_quote": c.volume_quote,
                    }
                )

    if not rows:
        return

    async with sessionmanager.session() as session:
        stmt = insert(Candle).values(rows)
        # Upsert (PostgreSQL)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_candles_identity")
        await session.execute(stmt)
        await session.commit()

