from __future__ import annotations

import asyncio

import structlog

from project.core.config import settings
from project.marketdata.api.bybit import collect_orderbook_walls_for_markets as collect_bybit_orderbook_walls
from project.marketdata.api.kucoin import collect_orderbook_walls_for_markets as collect_kucoin_orderbook_walls
from project.marketdata.dto import NormalizedMarket
from project.repositories.orderbook_walls import OrderBookWallRepository
from project.repositories.users import UserTrackedAssetRepository


logger = structlog.get_logger(__name__)


class OrderBookWallsService:
    async def ingest_tracked_orderbook_walls(self, *, duration_s: float = 20.0, max_markets: int = 10) -> int:
        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()

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

        await OrderBookWallRepository().bulk_insert_ignore_conflicts(
            rows,
            conflict_constraint="uq_orderbook_wall_identity",
        )

        logger.info("orderbook walls attempted", candidates=len(rows))
        return len(rows)
