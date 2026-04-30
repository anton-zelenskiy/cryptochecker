from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BigMoveMetrics:
    pct_change: float
    range_pct: float


def floor_time(ts: dt.datetime, *, seconds: int) -> dt.datetime:
    epoch = int(ts.timestamp())
    floored = epoch - (epoch % seconds)
    return dt.datetime.fromtimestamp(floored, tz=dt.timezone.utc)


def compute_big_move_metrics(*, prev_close: float, latest_close: float, latest_high: float, latest_low: float) -> BigMoveMetrics:
    if prev_close <= 0:
        raise ValueError("prev_close must be > 0")
    pct_change = (latest_close - prev_close) / prev_close * 100.0
    range_pct = (latest_high - latest_low) / prev_close * 100.0
    return BigMoveMetrics(pct_change=float(pct_change), range_pct=float(range_pct))


def passes_big_move_gate(
    metrics: BigMoveMetrics,
    *,
    threshold_pct: float,
    range_multiplier: float = 1.25,
) -> bool:
    return abs(metrics.pct_change) >= threshold_pct or metrics.range_pct >= (threshold_pct * range_multiplier)

