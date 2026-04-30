from __future__ import annotations

import datetime as dt

import structlog
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from project.core.db_session import sessionmanager
from project.models.trade_clusters import TradeCluster


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

        sql = text(
            """
            WITH t AS (
              SELECT
                source,
                base_asset,
                quote_asset,
                trade_time_utc,
                notional_quote,
                floor(extract(epoch from trade_time_utc) / :window_s)::bigint AS bucket
              FROM market_trades
              WHERE trade_time_utc >= :start
                AND side = 'buy'
                AND notional_quote >= :min_trade_notional
            ),
            c AS (
              SELECT
                source,
                base_asset,
                quote_asset,
                bucket,
                sum(notional_quote) AS buy_notional_quote,
                count(*)::int AS trade_count
              FROM t
              GROUP BY 1,2,3,4
              HAVING sum(notional_quote) >= :min_cluster_notional
            )
            SELECT source, base_asset, quote_asset, bucket, buy_notional_quote, trade_count
            FROM c
            """
        )

        async with sessionmanager.session() as session:
            res = await session.execute(
                sql,
                {
                    "start": start,
                    "window_s": window_s,
                    "min_trade_notional": min_trade_notional,
                    "min_cluster_notional": min_cluster_notional,
                },
            )
            clusters = list(res.mappings().all())

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

            stmt = insert(TradeCluster).values(rows)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_trade_cluster_identity")
            await session.execute(stmt)
            await session.commit()

        logger.info("trade clusters attempted", candidates=len(rows))
        return len(rows)
