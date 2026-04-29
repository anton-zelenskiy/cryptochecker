from __future__ import annotations

import datetime as dt

import pandas as pd
import structlog
from sqlalchemy import insert, select

from project.core.db_session import sessionmanager
from project.models.candles import Candle
from project.models.indicators import IndicatorSnapshot


logger = structlog.get_logger(__name__)


async def compute_rsi_14_snapshot(
    *,
    source: str,
    base_asset: str,
    quote_asset: str,
    timeframe: str,
    limit: int = 200,
) -> IndicatorSnapshot | None:
    """
    Compute RSI(14) for the latest candles and persist a snapshot.
    """
    from ta.momentum import RSIIndicator

    async with sessionmanager.session() as session:
        res = await session.execute(
            select(Candle)
            .where(Candle.source == source)
            .where(Candle.base_asset == base_asset)
            .where(Candle.quote_asset == quote_asset)
            .where(Candle.timeframe == timeframe)
            .order_by(Candle.open_time_utc.desc())
            .limit(limit)
        )
        candles = list(res.scalars().all())

    if len(candles) < 20:
        return None

    candles.sort(key=lambda c: c.open_time_utc)
    close = pd.Series([c.close for c in candles], dtype="float64")
    rsi = RSIIndicator(close=close, window=14).rsi()
    rsi_val = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None

    asof = candles[-1].open_time_utc
    row = {
        "source": source,
        "base_asset": base_asset,
        "quote_asset": quote_asset,
        "timeframe": timeframe,
        "asof_time_utc": asof,
        "rsi_14": rsi_val,
    }

    async with sessionmanager.session() as session:
        stmt = insert(IndicatorSnapshot).values(row)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_indicator_snapshot_identity")
        await session.execute(stmt)
        await session.commit()

        res = await session.execute(
            select(IndicatorSnapshot)
            .where(IndicatorSnapshot.source == source)
            .where(IndicatorSnapshot.base_asset == base_asset)
            .where(IndicatorSnapshot.quote_asset == quote_asset)
            .where(IndicatorSnapshot.timeframe == timeframe)
            .where(IndicatorSnapshot.asof_time_utc == asof)
        )
        snap = res.scalar_one_or_none()

    logger.info("rsi snapshot computed", source=source, base_asset=base_asset, timeframe=timeframe, rsi=rsi_val)
    return snap

