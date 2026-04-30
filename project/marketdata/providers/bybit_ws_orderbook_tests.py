from __future__ import annotations

import datetime as dt

import pytest

from project.marketdata.providers.bybit_ws_orderbook import (
    _parse_levels,
    _parse_ts_ms,
    pick_support_wall,
)


def test_pick_support_wall_detects_large_notional_outlier() -> None:
    bids = [
        (100.0, 1.0),
        (99.9, 1.1),
        (99.8, 1.0),
        (99.7, 1.0),
        (99.6, 1.0),
        (99.5, 25.0),
    ]
    picked = pick_support_wall(bids, min_notional_quote=2_000.0, qty_vs_median_multiplier=5.0, top_n=50)
    assert picked is not None
    wall_price, wall_qty, wall_notional, best_bid, median_qty = picked
    assert best_bid == 100.0
    assert wall_price == 99.5
    assert wall_qty == 25.0
    assert wall_notional == pytest.approx(99.5 * 25.0)
    assert median_qty > 0


def test_pick_support_wall_returns_none_when_no_levels() -> None:
    assert pick_support_wall([]) is None


def test_parse_levels_accepts_string_arrays() -> None:
    assert _parse_levels([["1.5", "2"], ["bad"], ["3", "not-a-number"]]) == [(1.5, 2.0)]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1672304484978, 1672304484978),
        ("1672304484978.0", 1672304484978),
        (None, None),
        ("x", None),
    ],
)
def test_parse_ts_ms(value: object, expected: int | None) -> None:
    assert _parse_ts_ms(value) == expected


def test_bucket_timestamp_roundtrip_example() -> None:
    ts_ms = 1672304484978
    bucket = int(ts_ms // 1000 // 15)
    start = dt.datetime.fromtimestamp(bucket * 15, tz=dt.timezone.utc)
    assert start.tzinfo is not None
