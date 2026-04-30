from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from project.core.repository import BaseRepository
from project.models.indicators import IndicatorSnapshot


class IndicatorSnapshotRepository(BaseRepository[IndicatorSnapshot]):
    def __init__(self) -> None:
        super().__init__(IndicatorSnapshot)

    async def get_latest(
        self, *, source: str, base_asset: str, quote_asset: str, timeframe: str
    ) -> IndicatorSnapshot | None:
        async with self._sessionmanager.session() as session:
            res = await session.execute(
                select(IndicatorSnapshot)
                .where(IndicatorSnapshot.source == source)
                .where(IndicatorSnapshot.base_asset == base_asset)
                .where(IndicatorSnapshot.quote_asset == quote_asset)
                .where(IndicatorSnapshot.timeframe == timeframe)
                .order_by(IndicatorSnapshot.asof_time_utc.desc())
                .limit(1)
            )
            return res.scalar_one_or_none()

    async def insert_ignore_conflict(self, row: dict, *, conflict_constraint: str) -> int:
        async with self._sessionmanager.session() as session:
            stmt = insert(IndicatorSnapshot).values(row)
            stmt = stmt.on_conflict_do_nothing(constraint=conflict_constraint)
            res = await session.execute(stmt)
            await session.commit()
            return int(getattr(res, "rowcount", 0) or 0)

    async def get_by_asof(
        self,
        *,
        source: str,
        base_asset: str,
        quote_asset: str,
        timeframe: str,
        asof_time_utc,
    ) -> IndicatorSnapshot | None:
        async with self._sessionmanager.session() as session:
            res = await session.execute(
                select(IndicatorSnapshot)
                .where(IndicatorSnapshot.source == source)
                .where(IndicatorSnapshot.base_asset == base_asset)
                .where(IndicatorSnapshot.quote_asset == quote_asset)
                .where(IndicatorSnapshot.timeframe == timeframe)
                .where(IndicatorSnapshot.asof_time_utc == asof_time_utc)
            )
            return res.scalar_one_or_none()

