from __future__ import annotations

import pytest

from project.screener.contracts import VolumeRegimeFeature
from project.screener.dynamic_market_thresholds import (
    AVG_DAILY_VOLUME_TO_MIN_NOTIONAL_RATIO,
    DEFAULT_ASSUMED_AVG_DAILY_VOLUME_QUOTE,
    DYNAMIC_MIN_NOTIONAL_CAP,
    DYNAMIC_MIN_NOTIONAL_FLOOR,
    MEDIAN_RANGE_WIDE_THRESHOLD,
    dynamic_wall_thresholds_for_market,
)


def test_min_notional_caps_for_very_high_daily_volume() -> None:
    vf = VolumeRegimeFeature(avg_daily_volume_quote=500_000_000.0)
    mn, _ = dynamic_wall_thresholds_for_market(vol_feat=vf, median_range_pct=None)
    assert mn == pytest.approx(DYNAMIC_MIN_NOTIONAL_CAP, rel=0.01)


def test_min_notional_without_avg_daily_uses_default_liquidity_assumption() -> None:
    vf = VolumeRegimeFeature(note="no_candles")
    mn, _ = dynamic_wall_thresholds_for_market(vol_feat=vf, median_range_pct=None)
    expected = max(
        DYNAMIC_MIN_NOTIONAL_FLOOR,
        min(
            DYNAMIC_MIN_NOTIONAL_CAP,
            DEFAULT_ASSUMED_AVG_DAILY_VOLUME_QUOTE * AVG_DAILY_VOLUME_TO_MIN_NOTIONAL_RATIO,
        ),
    )
    assert mn == pytest.approx(expected, rel=0.01)


def test_wide_intraday_range_raises_min_notional() -> None:
    vf = VolumeRegimeFeature(avg_daily_volume_quote=50_000_000.0)
    baseline, _ = dynamic_wall_thresholds_for_market(vol_feat=vf, median_range_pct=None)
    wide, _ = dynamic_wall_thresholds_for_market(
        vol_feat=vf,
        median_range_pct=MEDIAN_RANGE_WIDE_THRESHOLD + 0.01,
    )
    assert wide > baseline
