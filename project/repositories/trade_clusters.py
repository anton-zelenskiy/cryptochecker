from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from project.core.db_session import sessionmanager
from project.models.trade_clusters import TradeCluster


class TradeClustersRepository:
    async def list_recent_large_buy_clusters(
        self,
        *,
        start: dt.datetime,
        window_s: int,
        min_trade_notional: float,
        min_cluster_notional: float,
    ) -> list[dict]:
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
            return list(res.mappings().all())

    async def count_recent_for_market(
        self,
        *,
        base_asset: str,
        quote_asset: str,
        since: dt.datetime,
    ) -> int:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(func.count())
                .select_from(TradeCluster)
                .where(TradeCluster.base_asset == base_asset)
                .where(TradeCluster.quote_asset == quote_asset)
                .where(TradeCluster.detected_at >= since)
            )
            return int(res.scalar_one() or 0)

    async def bulk_insert_ignore_conflicts(self, rows: list[dict], *, conflict_constraint: str) -> int:
        if not rows:
            return 0
        async with sessionmanager.session() as session:
            stmt = insert(TradeCluster).values(rows)
            stmt = stmt.on_conflict_do_nothing(constraint=conflict_constraint)
            res = await session.execute(stmt)
            await session.commit()
            return int(getattr(res, "rowcount", 0) or 0)

