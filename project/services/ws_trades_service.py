from __future__ import annotations

import structlog

from project.core.config import settings
from project.marketdata.dto import NormalizedMarket
from project.marketdata.providers.bybit_ws_trades import collect_trades_for_markets
from project.repositories.market_trades import MarketTradeRepository
from project.repositories.users import UserTrackedAssetRepository


logger = structlog.get_logger(__name__)


class WsTradesService:
    async def ingest_tracked_trades_ws(self, *, duration_s: float = 20.0, max_markets: int = 20) -> int:
        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()
        if not markets:
            return 0

        normalized = [NormalizedMarket(base_asset=b, quote_asset=q) for b, q in sorted(markets)]
        extra_headers = {"X-BAPI-API-KEY": settings.BYBIT_API_KEY} if settings.BYBIT_API_KEY else None
        rows = await collect_trades_for_markets(
            normalized,
            duration_s=duration_s,
            max_markets=max_markets,
            extra_headers=extra_headers,
        )
        if not rows:
            return 0

        inserted = await MarketTradeRepository().bulk_insert_ignore_conflicts(
            rows,
            conflict_constraint="uq_market_trades_identity",
        )
        logger.info("market trades ingested", rows=len(rows), inserted=inserted)
        return inserted

