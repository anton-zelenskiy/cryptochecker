from __future__ import annotations

import pytest

from project.screener.contracts import FvgNearbyFeature, PerTimeframeIndicators, ScreenerFeaturesV1
from project.screener.risk import select_atr, suggest_trade_levels


@pytest.fixture
def features_with_atr() -> ScreenerFeaturesV1:
    return ScreenerFeaturesV1(
        source="kucoin",
        base_asset="BTC",
        quote_asset="USDT",
        asof_time_utc="2026-01-01T00:00:00+00:00",
        per_tf_indicators={
            "1h": PerTimeframeIndicators(timeframe="1h", atr_14=10.0),
        },
    )


def test_select_atr_prefers_1h(features_with_atr: ScreenerFeaturesV1) -> None:
    atr, tf = select_atr(features_with_atr)
    assert atr == 10.0
    assert tf == "1h"


@pytest.mark.parametrize(
    ("decision", "entry", "atr", "expected_sl", "expected_tp"),
    [
        ("LONG", 100.0, 10.0, 85.0, 130.0),  # risk=1.5*10=15, TP=entry+2*risk
        ("SHORT", 100.0, 10.0, 115.0, 70.0),  # TP=entry-2*risk
    ],
)
def test_suggest_trade_levels_baseline(decision: str, entry: float, atr: float, expected_sl: float, expected_tp: float) -> None:
    sug = suggest_trade_levels(
        decision=decision,  # type: ignore[arg-type]
        entry=entry,
        atr=atr,
        atr_timeframe="1h",
        fvg=None,
    )
    assert sug.method == "atr_baseline"
    assert sug.stop_loss == expected_sl
    assert sug.take_profit == expected_tp
    assert sug.risk_r == 2.0


def test_fvg_snap_long_applies_when_aligned_and_reasonable() -> None:
    # Baseline risk = 15, baseline SL = 85.
    # FVG zone_low=92 => tighter SL, should snap.
    fvg = FvgNearbyFeature(
        timeframe="15m",
        direction="bull",
        zone_low=92.0,
        zone_high=95.0,
        distance_pct_to_mid=1.0,
        is_unfilled=True,
    )
    sug = suggest_trade_levels(
        decision="LONG",
        entry=100.0,
        atr=10.0,
        atr_timeframe="1h",
        fvg=fvg,
    )
    assert sug.method == "atr_plus_fvg_snap"
    assert sug.stop_loss == 92.0
    assert sug.take_profit == 116.0  # risk=8 => TP=100+16


def test_fvg_snap_short_applies_when_aligned_and_reasonable() -> None:
    fvg = FvgNearbyFeature(
        timeframe="15m",
        direction="bear",
        zone_low=105.0,
        zone_high=108.0,
        distance_pct_to_mid=1.0,
        is_unfilled=True,
    )
    sug = suggest_trade_levels(
        decision="SHORT",
        entry=100.0,
        atr=10.0,
        atr_timeframe="1h",
        fvg=fvg,
    )
    assert sug.method == "atr_plus_fvg_snap"
    assert sug.stop_loss == 108.0
    assert sug.take_profit == 84.0  # risk=8 => TP=100-16


def test_fvg_snap_guard_blocks_absurdly_wide_sl() -> None:
    # Baseline risk=15. Candidate risk=70, candidate pct=70%.
    # With stricter guards, we should *not* snap.
    fvg = FvgNearbyFeature(
        timeframe="15m",
        direction="bull",
        zone_low=30.0,
        zone_high=40.0,
        distance_pct_to_mid=1.0,
        is_unfilled=True,
    )
    sug = suggest_trade_levels(
        decision="LONG",
        entry=100.0,
        atr=10.0,
        atr_timeframe="1h",
        fvg=fvg,
        snap_max_pct=0.04,
        snap_max_risk_mult=2.0,
    )
    assert sug.method == "atr_baseline"
    assert sug.stop_loss == 85.0

