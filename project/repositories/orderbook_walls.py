from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from project.core.db_session import sessionmanager
from project.models.orderbook_walls import OrderBookWall


class OrderBookWallRepository:
    async def bulk_insert_ignore_conflicts(self, rows: list[dict], *, conflict_constraint: str) -> int:
        if not rows:
            return 0
        async with sessionmanager.session() as session:
            stmt = insert(OrderBookWall).values(rows)
            stmt = stmt.on_conflict_do_nothing(constraint=conflict_constraint)
            res = await session.execute(stmt)
            await session.commit()
            return int(getattr(res, "rowcount", 0) or 0)

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
                .select_from(OrderBookWall)
                .where(OrderBookWall.base_asset == base_asset)
                .where(OrderBookWall.quote_asset == quote_asset)
                .where(OrderBookWall.detected_at >= since)
            )
            return int(res.scalar_one() or 0)

