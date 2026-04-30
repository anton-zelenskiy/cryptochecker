from __future__ import annotations

import datetime as dt

import pandas as pd
import structlog

from project.models.indicators import IndicatorSnapshot
from project.repositories.candles import CandleRepository
from project.repositories.indicators import IndicatorSnapshotRepository


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

    candle_repo = CandleRepository()
    candles = await candle_repo.list_latest_n(
        source=source,
        base_asset=base_asset,
        quote_asset=quote_asset,
        timeframe=timeframe,
        limit=limit,
    )

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

    repo = IndicatorSnapshotRepository()
    await repo.insert_ignore_conflict(row, conflict_constraint="uq_indicator_snapshot_identity")
    snap = await repo.get_by_asof(
        source=source,
        base_asset=base_asset,
        quote_asset=quote_asset,
        timeframe=timeframe,
        asof_time_utc=asof,
    )

    logger.info("rsi snapshot computed", source=source, base_asset=base_asset, timeframe=timeframe, rsi=rsi_val)
    return snap

