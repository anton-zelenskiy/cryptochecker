from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from project.marketdata.timeframes import TrendPullbackConfig
from project.services.volatility_service import (
    BigMoveMetrics,
    INDICATOR_CONTEXT_TF_ORDER,
    _core_indicators_from_indicator_snapshot,
    _streak_window_metrics,
    compute_big_move_metrics,
    detect_trend_with_pullback,
    detect_trend_streak_formation,
    floor_time,
    passes_big_move_gate,
)


def _c(o: float, h: float, l: float, c: float) -> SimpleNamespace:
    return SimpleNamespace(open=o, high=h, low=l, close=c)


def test_indicator_context_tf_order_prefers_higher_tf() -> None:
    assert INDICATOR_CONTEXT_TF_ORDER[0] == "1h"
    assert "5m" in INDICATOR_CONTEXT_TF_ORDER


def test_core_indicators_from_indicator_snapshot() -> None:
    snap = SimpleNamespace(rsi_14=55.0, macd_hist=0.01, adx_14=22.0)
    assert _core_indicators_from_indicator_snapshot(snap) == (55.0, 0.01, 22.0)
    assert _core_indicators_from_indicator_snapshot(None) == (None, None, None)
    assert _core_indicators_from_indicator_snapshot(SimpleNamespace(rsi_14=None)) == (None, None, None)


def test_floor_time_5m_bucket() -> None:
    ts = dt.datetime(2026, 1, 1, 0, 7, 59, tzinfo=dt.timezone.utc)
    bucket = floor_time(ts, seconds=300)
    assert bucket == dt.datetime(2026, 1, 1, 0, 5, 0, tzinfo=dt.timezone.utc)


def test_compute_big_move_metrics() -> None:
    m = compute_big_move_metrics(prev_close=100.0, latest_close=103.0, latest_high=104.0, latest_low=99.0)
    assert m.pct_change == pytest.approx(3.0)
    assert m.range_pct == pytest.approx(5.0)


def test_compute_big_move_metrics_invalid_prev_close() -> None:
    with pytest.raises(ValueError):
        compute_big_move_metrics(prev_close=0.0, latest_close=1.0, latest_high=1.0, latest_low=1.0)


@pytest.mark.parametrize(
    ("metrics", "threshold", "expected"),
    [
        (BigMoveMetrics(pct_change=2.0, range_pct=0.0), 2.0, True),
        (BigMoveMetrics(pct_change=-2.1, range_pct=0.0), 2.0, True),
        (BigMoveMetrics(pct_change=1.99, range_pct=0.0), 2.0, False),
        (BigMoveMetrics(pct_change=0.1, range_pct=2.5), 2.0, True),  # range gate (2.0 * 1.25)
        (BigMoveMetrics(pct_change=0.1, range_pct=2.49), 2.0, False),
    ],
)
def test_passes_big_move_gate(metrics: BigMoveMetrics, threshold: float, expected: bool) -> None:
    assert passes_big_move_gate(metrics, threshold_pct=threshold) is expected


def test_detect_trend_streak_formation_three_green_no_prior() -> None:
    chrono = [_c(100, 101, 99, 100.5), _c(100.5, 102, 100, 101), _c(101, 103, 100.5, 102)]
    assert detect_trend_streak_formation(chrono, min_streak=3) == "green"


def test_detect_trend_streak_formation_four_green_same_streak_no_alert() -> None:
    chrono = [
        _c(100, 101, 99, 100.5),
        _c(100.5, 102, 100, 101),
        _c(101, 103, 100.5, 102),
        _c(102, 104, 101.5, 103),
    ]
    assert detect_trend_streak_formation(chrono, min_streak=3) is None


def test_detect_trend_streak_formation_after_red() -> None:
    chrono = [
        _c(105, 105, 100, 101),
        _c(101, 102, 100.5, 101.5),
        _c(101.5, 103, 101, 102.5),
        _c(102.5, 104, 102, 103.5),
    ]
    assert detect_trend_streak_formation(chrono, min_streak=3) == "green"


def test_detect_trend_streak_formation_three_red() -> None:
    chrono = [_c(102, 102, 100, 101), _c(101, 101, 99, 99.5), _c(99.5, 100, 98, 98.5)]
    assert detect_trend_streak_formation(chrono, min_streak=3) == "red"


def test_detect_trend_streak_formation_doji_tail() -> None:
    chrono = [_c(100, 101, 99, 100.5), _c(100.5, 102, 100, 101), _c(101, 101, 101, 101)]
    assert detect_trend_streak_formation(chrono, min_streak=3) is None


def test_streak_window_metrics() -> None:
    chrono = [_c(100, 101, 99, 100.5), _c(100.5, 102, 100, 101), _c(101, 103, 100.5, 102)]
    m = _streak_window_metrics(chrono, tail_n=3)
    assert m.pct_change == pytest.approx(2.0)
    assert m.range_pct == pytest.approx(4.0)


def test_detect_trend_with_pullback_green_pullback_then_resume() -> None:
    cfg = TrendPullbackConfig(
        timeframe="1h",
        window_candles=6,
        min_impulse_green=3,
        min_impulse_red=3,
        max_pullback_red=1,
        max_pullback_green=1,
        continuation_candles=2,
        majority_ratio=0.6,
        min_net_pct_abs=0.0,
    )
    chrono = [
        _c(100, 101, 99, 101),  # G
        _c(101, 102, 100, 102),  # G
        _c(102, 103, 101, 103),  # G
        _c(103, 104, 100, 102),  # R pullback
        _c(102, 103, 101, 103),  # G resume
        _c(103, 104, 102, 104),  # G resume
    ]
    detected = detect_trend_with_pullback(chrono, cfg=cfg)
    assert detected is not None
    direction, payload = detected
    assert direction == "green"
    assert payload["green_count"] >= 3
    assert payload["red_count"] <= 1


def test_detect_trend_with_pullback_requires_continuation() -> None:
    cfg = TrendPullbackConfig(
        timeframe="1h",
        window_candles=6,
        min_impulse_green=3,
        min_impulse_red=3,
        max_pullback_red=1,
        max_pullback_green=1,
        continuation_candles=2,
        majority_ratio=0.6,
        min_net_pct_abs=0.0,
    )
    chrono = [
        _c(100, 101, 99, 101),  # G
        _c(101, 102, 100, 102),  # G
        _c(102, 103, 101, 103),  # G
        _c(103, 104, 100, 102),  # R pullback
        _c(102, 103, 101, 103),  # only 1 green after pullback
        _c(103, 103, 101, 102),  # R again (break continuation)
    ]
    assert detect_trend_with_pullback(chrono, cfg=cfg) is None


def test_detect_trend_with_pullback_transition_only() -> None:
    cfg = TrendPullbackConfig(
        timeframe="1h",
        window_candles=6,
        min_impulse_green=3,
        min_impulse_red=3,
        max_pullback_red=1,
        max_pullback_green=1,
        continuation_candles=2,
        majority_ratio=0.6,
        min_net_pct_abs=0.0,
    )
    # First window qualifies (should signal)
    chrono = [
        _c(100, 101, 99, 101),
        _c(101, 102, 100, 102),
        _c(102, 103, 101, 103),
        _c(103, 104, 100, 102),
        _c(102, 103, 101, 103),
        _c(103, 104, 102, 104),
    ]
    assert detect_trend_with_pullback(chrono, cfg=cfg) is not None

    # Next candle keeps trend qualified; detector should not fire again.
    chrono2 = chrono + [_c(104, 105, 103, 105)]
    assert detect_trend_with_pullback(chrono2, cfg=cfg) is None
