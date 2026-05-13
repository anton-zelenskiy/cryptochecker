from __future__ import annotations

import structlog

from project.models.indicators import IndicatorSnapshot
from project.repositories.candles import CandleRepository
from project.repositories.indicators import IndicatorSnapshotRepository
from project.screener.indicators_bundle import compute_indicator_bundle_row


logger = structlog.get_logger(__name__)


async def compute_indicator_bundle_snapshot(
    *,
    source: str,
    base_asset: str,
    quote_asset: str,
    timeframe: str,
    limit: int = 400,
) -> IndicatorSnapshot | None:
    candle_repo = CandleRepository()
    candles = await candle_repo.list_latest_n(
        source=source,
        base_asset=base_asset,
        quote_asset=quote_asset,
        timeframe=timeframe,
        limit=limit,
    )
    if len(candles) < 60:
        return None

    candles.sort(key=lambda c: c.open_time_utc)
    high = [float(c.high) for c in candles]
    low = [float(c.low) for c in candles]
    close = [float(c.close) for c in candles]
    vol = []
    for c in candles:
        if c.volume_quote is not None and c.volume_quote > 0:
            vol.append(float(c.volume_quote))
        elif c.volume_base is not None:
            vol.append(float(c.volume_base))
        else:
            vol.append(0.0)

    bundle = compute_indicator_bundle_row(high=high, low=low, close=close, volume=vol)
    if not bundle:
        return None

    asof = candles[-1].open_time_utc

    row = {
        "source": source,
        "base_asset": base_asset,
        "quote_asset": quote_asset,
        "timeframe": timeframe,
        "asof_time_utc": asof,
        **bundle,
    }

    repo = IndicatorSnapshotRepository()
    await repo.insert_ignore_conflict(row, conflict_constraint="uq_indicator_snapshot_identity")
    return await repo.get_by_asof(
        source=source,
        base_asset=base_asset,
        quote_asset=quote_asset,
        timeframe=timeframe,
        asof_time_utc=asof,
    )

