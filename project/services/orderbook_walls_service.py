from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from project.core.config import settings
from project.core.db_session import sessionmanager
from project.marketdata.dto import NormalizedMarket
from project.marketdata.providers.bybit_ws_orderbook import collect_orderbook_walls_for_markets as collect_bybit_orderbook_walls
from project.marketdata.providers.kucoin_ws_orderbook import collect_orderbook_walls_for_markets as collect_kucoin_orderbook_walls
from project.models.orderbook_walls import OrderBookWall
from project.models.users import UserTrackedAsset


logger = structlog.get_logger(__name__)


class OrderBookWallsService:
    async def ingest_tracked_orderbook_walls(self, *, duration_s: float = 20.0, max_markets: int = 10) -> int:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(UserTrackedAsset.base_asset, UserTrackedAsset.quote_asset)
                .where(UserTrackedAsset.enabled.is_(True))
                .distinct()
            )
            markets = [(str(b), str(q)) for b, q in res.all()]

        if not markets:
            return 0

        normalized = [NormalizedMarket(base_asset=b, quote_asset=q) for b, q in sorted(markets)]
        bybit_headers = {"X-BAPI-API-KEY": settings.BYBIT_API_KEY} if settings.BYBIT_API_KEY else None
        kucoin_headers = None
        if settings.KUCOIN_API_KEY:
            kucoin_headers = {"KC-API-KEY": settings.KUCOIN_API_KEY}

        bybit_rows, kucoin_rows = await asyncio.gather(
            collect_bybit_orderbook_walls(
                normalized,
                duration_s=duration_s,
                max_markets=max_markets,
                extra_headers=bybit_headers,
            ),
            collect_kucoin_orderbook_walls(
                normalized,
                duration_s=duration_s,
                max_markets=max_markets,
                extra_headers=kucoin_headers,
            ),
        )
        rows = [*bybit_rows, *kucoin_rows]
        if not rows:
            return 0

        async with sessionmanager.session() as session:
            stmt = insert(OrderBookWall).values(rows)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_orderbook_wall_identity")
            await session.execute(stmt)
            await session.commit()

        logger.info("orderbook walls attempted", candidates=len(rows))
        return len(rows)
