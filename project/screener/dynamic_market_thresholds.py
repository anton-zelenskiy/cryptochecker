from __future__ import annotations

from typing import Protocol

# When avg daily quote volume is missing or invalid, assume deep liquidity (USD quote).
DEFAULT_ASSUMED_AVG_DAILY_VOLUME_QUOTE = 50_000_000.0

# Map assumed daily volume to a baseline min wall/trade notional (quote currency).
AVG_DAILY_VOLUME_TO_MIN_NOTIONAL_RATIO = 0.0003

# Clamp dynamic min-notional to stay interpretable across micro-caps and mega-caps.
DYNAMIC_MIN_NOTIONAL_FLOOR = 5_000.0
DYNAMIC_MIN_NOTIONAL_CAP = 150_000.0

# Median hourly range (high-low)/close used to scale thresholds vs chop vs expansion.
MEDIAN_RANGE_WIDE_THRESHOLD = 0.05
MEDIAN_RANGE_TIGHT_THRESHOLD = 0.02

VOL_FACTOR_WIDE_RANGE = 1.5
VOL_FACTOR_NEUTRAL = 1.0
VOL_FACTOR_TIGHT_RANGE = 0.85

SPIKE_MIN_NOTIONAL_MULTIPLIER = 1.2
NO_SPIKE_MIN_NOTIONAL_MULTIPLIER = 1.0

QTY_VS_MEDIAN_BASE = 6.0
QTY_VS_MEDIAN_WIDE_RANGE_BUMP = 2.0
QTY_VS_MEDIAN_TIGHT_RANGE_TRIM = 1.0
QTY_VS_MEDIAN_SPIKE_TRIM = 0.75
QTY_VS_MEDIAN_MIN = 4.0
QTY_VS_MEDIAN_MAX = 10.0


class _CandleCloseRange(Protocol):
    high: float
    low: float
    close: float


def range_pct_from_candle(c: _CandleCloseRange) -> float | None:
    if not c.close:
        return None
    try:
        return float(c.high - c.low) / float(c.close)
    except Exception:
        return None


def dynamic_wall_thresholds_for_market(
    *,
    vol_feat: object,
    median_range_pct: float | None,
) -> tuple[float, float]:
    avg_daily = getattr(vol_feat, "avg_daily_volume_quote", None)
    if avg_daily is None or avg_daily <= 0:
        avg_daily = DEFAULT_ASSUMED_AVG_DAILY_VOLUME_QUOTE

    base_min_notional = max(
        DYNAMIC_MIN_NOTIONAL_FLOOR,
        min(
            DYNAMIC_MIN_NOTIONAL_CAP,
            float(avg_daily) * AVG_DAILY_VOLUME_TO_MIN_NOTIONAL_RATIO,
        ),
    )

    vol_factor = VOL_FACTOR_NEUTRAL
    if median_range_pct is not None:
        if median_range_pct >= MEDIAN_RANGE_WIDE_THRESHOLD:
            vol_factor = VOL_FACTOR_WIDE_RANGE
        elif median_range_pct <= MEDIAN_RANGE_TIGHT_THRESHOLD:
            vol_factor = VOL_FACTOR_TIGHT_RANGE

    spike = bool(getattr(vol_feat, "is_sharp_spike", False))
    spike_factor = SPIKE_MIN_NOTIONAL_MULTIPLIER if spike else NO_SPIKE_MIN_NOTIONAL_MULTIPLIER

    min_notional_quote = float(base_min_notional * vol_factor * spike_factor)

    qty_mult = QTY_VS_MEDIAN_BASE
    if median_range_pct is not None and median_range_pct >= MEDIAN_RANGE_WIDE_THRESHOLD:
        qty_mult += QTY_VS_MEDIAN_WIDE_RANGE_BUMP
    if median_range_pct is not None and median_range_pct <= MEDIAN_RANGE_TIGHT_THRESHOLD:
        qty_mult -= QTY_VS_MEDIAN_TIGHT_RANGE_TRIM
    if spike:
        qty_mult -= QTY_VS_MEDIAN_SPIKE_TRIM
    qty_vs_median_multiplier = float(max(QTY_VS_MEDIAN_MIN, min(QTY_VS_MEDIAN_MAX, qty_mult)))

    return min_notional_quote, qty_vs_median_multiplier
