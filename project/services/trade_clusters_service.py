from __future__ import annotations

import datetime as dt

import structlog

from project.repositories.trade_clusters import TradeClustersRepository


logger = structlog.get_logger(__name__)


class TradeClustersService:
    async def cluster_recent_large_buys(
        self,
        *,
        lookback_s: int = 120,
        window_s: int = 15,
        min_trade_notional: float = 25_000.0,
        min_cluster_notional: float = 100_000.0,
    ) -> int:
        now = dt.datetime.now(dt.timezone.utc)
        start = now - dt.timedelta(seconds=lookback_s)
        repo = TradeClustersRepository()
        clusters = await repo.list_recent_large_buy_clusters(
            start=start,
            window_s=window_s,
            min_trade_notional=min_trade_notional,
            min_cluster_notional=min_cluster_notional,
        )
        if not clusters:
            return 0

        rows = [
            {
                "source": r["source"],
                "base_asset": r["base_asset"],
                "quote_asset": r["quote_asset"],
                "window_start_utc": dt.datetime.fromtimestamp(
                    int(r["bucket"]) * window_s,
                    tz=dt.timezone.utc,
                ),
                "window_seconds": window_s,
                "buy_notional_quote": float(r["buy_notional_quote"]),
                "trade_count": int(r["trade_count"]),
                "detected_at": now,
            }
            for r in clusters
        ]
        await repo.bulk_insert_ignore_conflicts(rows, conflict_constraint="uq_trade_cluster_identity")

        logger.info("trade clusters attempted", candidates=len(rows))
        return len(rows)
