from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Timeframe(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str  # "1m", "5m", "1h", "1d", "1w"
    seconds: int


TF_1M = Timeframe(code="1m", seconds=60)
TF_5M = Timeframe(code="5m", seconds=5 * 60)
TF_15M = Timeframe(code="15m", seconds=15 * 60)
TF_1H = Timeframe(code="1h", seconds=60 * 60)
TF_4H = Timeframe(code="4h", seconds=4 * 60 * 60)
TF_1D = Timeframe(code="1d", seconds=24 * 60 * 60)
TF_1W = Timeframe(code="1w", seconds=7 * 24 * 60 * 60)


SUPPORTED_TIMEFRAMES: dict[str, Timeframe] = {
    tf.code: tf
    for tf in (TF_1M, TF_5M, TF_15M, TF_1H, TF_4H, TF_1D, TF_1W)
}


def normalize_timeframe(code: str) -> Timeframe:
    tf = SUPPORTED_TIMEFRAMES.get(code)
    if not tf:
        raise ValueError(f"Unsupported timeframe: {code}")
    return tf


class TrendPullbackConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    timeframe: str
    window_candles: int
    min_impulse_green: int
    min_impulse_red: int
    max_pullback_red: int
    max_pullback_green: int
    continuation_candles: int
    majority_ratio: float
    min_net_pct_abs: float = 0.0


TREND_PULLBACK_CONFIGS: dict[str, TrendPullbackConfig] = {
    "15m": TrendPullbackConfig(
        timeframe="15m",
        window_candles=16,  # ~4h
        min_impulse_green=3,
        min_impulse_red=3,
        max_pullback_red=2,
        max_pullback_green=2,
        continuation_candles=3,
        majority_ratio=0.70,
        min_net_pct_abs=0.5,
    ),
    "1h": TrendPullbackConfig(
        timeframe="1h",
        window_candles=10,  # ~10h
        min_impulse_green=3,
        min_impulse_red=3,
        max_pullback_red=1,
        max_pullback_green=1,
        continuation_candles=2,
        majority_ratio=0.65,
        min_net_pct_abs=0.75,
    ),
    "4h": TrendPullbackConfig(
        timeframe="4h",
        window_candles=8,  # ~32h
        min_impulse_green=3,
        min_impulse_red=3,
        max_pullback_red=1,
        max_pullback_green=1,
        continuation_candles=2,
        majority_ratio=0.62,
        min_net_pct_abs=1.0,
    ),
}

