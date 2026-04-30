from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert

from project.core.db_session import sessionmanager
from project.models.volatility_events import VolatilityEvent


class VolatilityEventRepository:
    async def insert_if_new(self, row: dict, *, conflict_constraint: str) -> bool:
        async with sessionmanager.session() as session:
            stmt = insert(VolatilityEvent).values([row])
            stmt = stmt.on_conflict_do_nothing(constraint=conflict_constraint)
            res = await session.execute(stmt)
            await session.commit()
            return int(getattr(res, "rowcount", 0) or 0) > 0

