from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Timeframe(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str  # "1m", "5m", "1h", "1d"
    seconds: int


TF_1M = Timeframe(code="1m", seconds=60)
TF_5M = Timeframe(code="5m", seconds=5 * 60)
TF_15M = Timeframe(code="15m", seconds=15 * 60)
TF_1H = Timeframe(code="1h", seconds=60 * 60)
TF_4H = Timeframe(code="4h", seconds=4 * 60 * 60)
TF_1D = Timeframe(code="1d", seconds=24 * 60 * 60)


SUPPORTED_TIMEFRAMES: dict[str, Timeframe] = {
    tf.code: tf
    for tf in (TF_1M, TF_5M, TF_15M, TF_1H, TF_4H, TF_1D)
}


def normalize_timeframe(code: str) -> Timeframe:
    tf = SUPPORTED_TIMEFRAMES.get(code)
    if not tf:
        raise ValueError(f"Unsupported timeframe: {code}")
    return tf

