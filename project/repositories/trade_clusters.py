from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from project.core.db_session import sessionmanager
from project.models.trade_clusters import TradeCluster


TradeClusterMarketThreshold = tuple[str, str, str, float, float]


class TradeClustersRepository:
    async def list_recent_large_buy_clusters(
        self,
        *,
        start: dt.datetime,
        window_s: int,
        thresholds: list[TradeClusterMarketThreshold],
    ) -> list[dict]:
        if not thresholds:
            return []

        sql = text(
            """
            WITH thresholds AS (
              SELECT *
              FROM unnest(
                CAST(:sources AS text[]),
                CAST(:bases AS text[]),
                CAST(:quotes AS text[]),
                CAST(:min_trade_notionals AS double precision[]),
                CAST(:min_cluster_notionals AS double precision[])
              ) AS t(source, base_asset, quote_asset, min_trade_notional, min_cluster_notional)
            ),
            trades AS (
              SELECT
                mt.source,
                mt.base_asset,
                mt.quote_asset,
                mt.notional_quote,
                th.min_cluster_notional,
                floor(extract(epoch from mt.trade_time_utc) / :window_s)::bigint AS bucket
              FROM market_trades mt
              INNER JOIN thresholds th
                ON mt.source = th.source
               AND mt.base_asset = th.base_asset
               AND mt.quote_asset = th.quote_asset
              WHERE mt.trade_time_utc >= :start
                AND mt.side = 'buy'
                AND mt.notional_quote >= th.min_trade_notional
            ),
            c AS (
              SELECT
                source,
                base_asset,
                quote_asset,
                bucket,
                sum(notional_quote) AS buy_notional_quote,
                count(*)::int AS trade_count
              FROM trades
              GROUP BY 1, 2, 3, 4
              HAVING sum(notional_quote) >= max(min_cluster_notional)
            )
            SELECT source, base_asset, quote_asset, bucket, buy_notional_quote, trade_count
            FROM c
            """
        )
        sources, bases, quotes, min_trade_notionals, min_cluster_notionals = zip(*thresholds)
        params = {
            "start": start,
            "window_s": window_s,
            "sources": list(sources),
            "bases": list(bases),
            "quotes": list(quotes),
            "min_trade_notionals": list(min_trade_notionals),
            "min_cluster_notionals": list(min_cluster_notionals),
        }
        async with sessionmanager.session() as session:
            res = await session.execute(sql, params)
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

