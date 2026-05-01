from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select

from project.core.db_session import sessionmanager
from project.models.candles import Candle

# asyncpg hard limit ~32767 bind parameters per statement; candles row uses ~11 columns.
_CANDLES_BULK_CHUNK_SIZE = 2500


class CandleRepository:
    async def bulk_insert_ignore_conflicts(
        self,
        rows: list[dict],
        *,
        conflict_constraint: str = "uq_candles_identity",
    ) -> int:
        if not rows:
            return 0

        inserted = 0
        async with sessionmanager.session() as session:
            for i in range(0, len(rows), _CANDLES_BULK_CHUNK_SIZE):
                chunk = rows[i : i + _CANDLES_BULK_CHUNK_SIZE]
                stmt = insert(Candle).values(chunk)
                stmt = stmt.on_conflict_do_nothing(constraint=conflict_constraint)
                res = await session.execute(stmt)
                inserted += int(getattr(res, "rowcount", 0) or 0)
            await session.commit()
        return inserted

    async def get_latest(self, *, source: str, base_asset: str, quote_asset: str, timeframe: str) -> Candle | None:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(Candle)
                .where(Candle.source == source)
                .where(Candle.base_asset == base_asset)
                .where(Candle.quote_asset == quote_asset)
                .where(Candle.timeframe == timeframe)
                .order_by(Candle.open_time_utc.desc())
                .limit(1)
            )
            return res.scalar_one_or_none()

    async def get_latest_two(
        self,
        *,
        source: str,
        base_asset: str,
        quote_asset: str,
        timeframe: str,
    ) -> tuple[Candle | None, Candle | None]:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(Candle)
                .where(Candle.source == source)
                .where(Candle.base_asset == base_asset)
                .where(Candle.quote_asset == quote_asset)
                .where(Candle.timeframe == timeframe)
                .order_by(Candle.open_time_utc.desc())
                .limit(2)
            )
            candles = list(res.scalars().all())
        if not candles:
            return None, None
        if len(candles) == 1:
            return candles[0], None
        return candles[0], candles[1]

    async def get_first_after_or_at(
        self,
        *,
        source: str,
        base_asset: str,
        quote_asset: str,
        timeframe: str,
        open_time_utc: object,
    ) -> Candle | None:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(Candle)
                .where(Candle.source == source)
                .where(Candle.base_asset == base_asset)
                .where(Candle.quote_asset == quote_asset)
                .where(Candle.timeframe == timeframe)
                .where(Candle.open_time_utc >= open_time_utc)
                .order_by(Candle.open_time_utc.asc())
                .limit(1)
            )
            return res.scalar_one_or_none()

    async def list_latest_n(
        self,
        *,
        source: str,
        base_asset: str,
        quote_asset: str,
        timeframe: str,
        limit: int,
    ) -> list[Candle]:
        if limit <= 0:
            return []
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(Candle)
                .where(Candle.source == source)
                .where(Candle.base_asset == base_asset)
                .where(Candle.quote_asset == quote_asset)
                .where(Candle.timeframe == timeframe)
                .order_by(Candle.open_time_utc.desc())
                .limit(int(limit))
            )
            return list(res.scalars().all())

