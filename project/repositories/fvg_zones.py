from __future__ import annotations

import datetime as dt

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from project.core.db_session import sessionmanager
from project.models.screener import FvgZone


class FvgZoneRepository:
    async def insert_ignore(self, row: dict) -> int:
        async with sessionmanager.session() as session:
            stmt = pg_insert(FvgZone).values(row)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_fvg_zone_identity")
            res = await session.execute(stmt)
            await session.commit()
            return int(getattr(res, "rowcount", 0) or 0)

    async def list_unmitigated(
        self,
        *,
        source: str,
        base_asset: str,
        quote_asset: str,
        timeframe: str,
    ) -> list[FvgZone]:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(FvgZone)
                .where(FvgZone.source == source)
                .where(FvgZone.base_asset == base_asset)
                .where(FvgZone.quote_asset == quote_asset)
                .where(FvgZone.timeframe == timeframe)
                .where(FvgZone.mitigated_at_utc.is_(None))
                .order_by(FvgZone.formed_at_open_time_utc.desc())
                .limit(50)
            )
            return list(res.scalars().all())

    async def set_mitigated(self, zone_id: int, *, at: dt.datetime) -> None:
        async with sessionmanager.session() as session:
            await session.execute(
                update(FvgZone)
                .where(FvgZone.id == zone_id)
                .values(mitigated_at_utc=at, updated_at=at)
            )
            await session.commit()
