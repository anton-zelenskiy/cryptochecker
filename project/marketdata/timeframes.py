from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Timeframe:
    code: str  # "1m", "5m", "1h", "1d"
    seconds: int


TF_1M = Timeframe("1m", 60)
TF_5M = Timeframe("5m", 5 * 60)
TF_15M = Timeframe("15m", 15 * 60)
TF_1H = Timeframe("1h", 60 * 60)
TF_4H = Timeframe("4h", 4 * 60 * 60)
TF_1D = Timeframe("1d", 24 * 60 * 60)


SUPPORTED_TIMEFRAMES: dict[str, Timeframe] = {
    tf.code: tf
    for tf in (TF_1M, TF_5M, TF_15M, TF_1H, TF_4H, TF_1D)
}


def normalize_timeframe(code: str) -> Timeframe:
    tf = SUPPORTED_TIMEFRAMES.get(code)
    if not tf:
        raise ValueError(f"Unsupported timeframe: {code}")
    return tf

