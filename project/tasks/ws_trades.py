from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import insert

from project.celery_app import celery_app
from project.core.db_session import sessionmanager
from project.marketdata.dto import NormalizedMarket
from project.marketdata.providers.bybit_ws_trades import collect_trades_for_markets
from project.models.market_trades import MarketTrade
from project.repositories.users import TelegramUserRepository, UserTrackedAssetRepository


logger = structlog.get_logger(__name__)


@celery_app.task(name="project.tasks.ws_trades.ingest_tracked_trades_ws")
def ingest_tracked_trades_ws() -> None:
    """
    Trades-only WS ingest slice.

    This is intentionally bounded (short runtime) and scheduled periodically, so we don't
    need a dedicated always-on daemon yet.
    """
    asyncio.run(_ingest())


async def _ingest() -> None:
    user_repo = TelegramUserRepository()
    tracked_repo = UserTrackedAssetRepository()

    users = await user_repo.get_all()
    markets: set[tuple[str, str]] = set()
    for u in users:
        assets = await tracked_repo.list_enabled_assets(u.id)
        for a in assets:
            markets.add((a.base_asset, a.quote_asset))

    if not markets:
        return

    normalized = [NormalizedMarket(base_asset=b, quote_asset=q) for b, q in sorted(markets)]
    rows = await collect_trades_for_markets(normalized, duration_s=20.0, max_markets=20)
    if not rows:
        return

    async with sessionmanager.session() as session:
        stmt = insert(MarketTrade).values(rows)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_market_trades_identity")
        await session.execute(stmt)
        await session.commit()

    logger.info("market trades ingested", rows=len(rows))

