from __future__ import annotations

import datetime as dt

import pytest

from project.services.volatility_service import (
    BigMoveMetrics,
    compute_big_move_metrics,
    floor_time,
    passes_big_move_gate,
)


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
