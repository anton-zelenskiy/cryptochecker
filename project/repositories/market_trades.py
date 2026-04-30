from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert

from project.core.db_session import sessionmanager
from project.models.market_trades import MarketTrade


class MarketTradeRepository:
    async def bulk_insert_ignore_conflicts(self, rows: list[dict], *, conflict_constraint: str) -> int:
        if not rows:
            return 0
        async with sessionmanager.session() as session:
            stmt = insert(MarketTrade).values(rows)
            stmt = stmt.on_conflict_do_nothing(constraint=conflict_constraint)
            res = await session.execute(stmt)
            await session.commit()
            return int(getattr(res, "rowcount", 0) or 0)

