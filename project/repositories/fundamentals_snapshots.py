from __future__ import annotations

from sqlalchemy import select

from project.core.db_session import sessionmanager
from project.models.screener import FundamentalsSnapshot


class FundamentalsSnapshotRepository:
    async def insert(self, row: dict) -> FundamentalsSnapshot:
        async with sessionmanager.session() as session:
            ent = FundamentalsSnapshot(**row)
            session.add(ent)
            await session.commit()
            await session.refresh(ent)
            return ent

    async def get_latest_for_coingecko_id(self, *, coingecko_id: str) -> FundamentalsSnapshot | None:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(FundamentalsSnapshot)
                .where(FundamentalsSnapshot.coingecko_id == coingecko_id)
                .order_by(FundamentalsSnapshot.fetched_at.desc())
                .limit(1)
            )
            return res.scalar_one_or_none()
