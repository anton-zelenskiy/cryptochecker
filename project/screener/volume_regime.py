from __future__ import annotations

import datetime as dt

import pandas as pd
from pydantic import BaseModel, ConfigDict

from project.screener.contracts import VolumeRegimeFeature


class CandleOHLCV(BaseModel):
    model_config = ConfigDict(frozen=True)

    open_time_utc: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume_quote: float | None
    volume_base: float | None


def _volume_quote(c: CandleOHLCV) -> float:
    if c.volume_quote is not None and c.volume_quote > 0:
        return float(c.volume_quote)
    if c.volume_base is not None and c.close:
        return float(c.volume_base) * float(c.close)
    return 0.0


def compute_volume_regime(
    candles: list[CandleOHLCV],
    *,
    lookback_days: int = 14,
    spike_ratio_threshold: float = 2.5,
    min_zscore: float = 2.0,
) -> VolumeRegimeFeature:
    if not candles:
        return VolumeRegimeFeature(lookback_days=lookback_days, note="no_candles")

    candles = sorted(candles, key=lambda x: x.open_time_utc)
    times = pd.DatetimeIndex([c.open_time_utc for c in candles], tz="UTC")
    vols = pd.Series([_volume_quote(c) for c in candles], dtype="float64")
    closes = pd.Series([c.close for c in candles], dtype="float64")

    df = pd.DataFrame({"t": times, "vol": vols, "close": closes})
    df = df.set_index("t").sort_index()

    daily = df["vol"].resample("1D").sum().dropna()
    if len(daily) < 3:
        avg = float(daily.mean()) if len(daily) else None
        latest = float(daily.iloc[-1]) if len(daily) else float(vols.iloc[-1])
        ratio = (latest / avg) if avg and avg > 0 else None
        z = None
        spike = bool(ratio and ratio >= spike_ratio_threshold)
        return VolumeRegimeFeature(
            avg_daily_volume_quote=avg,
            latest_daily_volume_quote=latest,
            volume_ratio_vs_avg=ratio,
            volume_zscore=z,
            is_sharp_spike=spike,
            lookback_days=lookback_days,
            note="insufficient_daily_bars",
        )

    tail = daily.tail(lookback_days + 1)
    if len(tail) < 4:
        avg = float(tail.iloc[:-1].mean()) if len(tail) > 1 else float(tail.mean())
        latest = float(tail.iloc[-1])
        ratio = (latest / avg) if avg > 0 else None
        return VolumeRegimeFeature(
            avg_daily_volume_quote=avg,
            latest_daily_volume_quote=latest,
            volume_ratio_vs_avg=ratio,
            volume_zscore=None,
            is_sharp_spike=bool(ratio and ratio >= spike_ratio_threshold),
            lookback_days=lookback_days,
            note="short_history",
        )

    hist = tail.iloc[:-1]
    latest = float(tail.iloc[-1])
    avg = float(hist.mean())
    std = float(hist.std(ddof=1)) if len(hist) > 1 else 0.0
    z = ((latest - avg) / std) if std > 1e-12 else None
    ratio = (latest / avg) if avg > 0 else None
    spike = bool(
        ratio is not None
        and ratio >= spike_ratio_threshold
        and (z is None or z >= min_zscore)
    )
    return VolumeRegimeFeature(
        avg_daily_volume_quote=avg,
        latest_daily_volume_quote=latest,
        volume_ratio_vs_avg=ratio,
        volume_zscore=z,
        is_sharp_spike=spike,
        lookback_days=lookback_days,
    )
