from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from project.paper_trading.exit import evaluate_exit


def _bar(open_time_utc: dt.datetime, low: float, high: float) -> SimpleNamespace:
    return SimpleNamespace(open_time_utc=open_time_utc, low=low, high=high)


def test_evaluate_exit_long_tp_hit():
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    trade = SimpleNamespace(side="LONG", stop_loss=90.0, take_profit=110.0)
    candles = [_bar(t0, 95.0, 115.0)]
    r = evaluate_exit(trade, candles)
    assert r is not None
    reason, px, ex_t = r
    assert reason == "tp_hit"
    assert px == 110.0
    assert ex_t == t0


def test_evaluate_exit_long_sl_hit():
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    trade = SimpleNamespace(side="LONG", stop_loss=90.0, take_profit=110.0)
    candles = [_bar(t0, 85.0, 95.0)]
    r = evaluate_exit(trade, candles)
    assert r is not None
    reason, px, _ = r
    assert reason == "sl_hit"
    assert px == 90.0


def test_evaluate_exit_long_both_in_bar_prefers_sl():
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    trade = SimpleNamespace(side="LONG", stop_loss=90.0, take_profit=110.0)
    candles = [_bar(t0, 85.0, 115.0)]
    r = evaluate_exit(trade, candles)
    assert r is not None
    assert r[0] == "sl_hit"


def test_evaluate_exit_short_tp_hit():
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    trade = SimpleNamespace(side="SHORT", stop_loss=110.0, take_profit=90.0)
    candles = [_bar(t0, 85.0, 95.0)]
    r = evaluate_exit(trade, candles)
    assert r is not None
    assert r[0] == "tp_hit"
    assert r[1] == 90.0


def test_evaluate_exit_short_sl_hit():
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    trade = SimpleNamespace(side="SHORT", stop_loss=110.0, take_profit=90.0)
    candles = [_bar(t0, 105.0, 115.0)]
    r = evaluate_exit(trade, candles)
    assert r is not None
    assert r[0] == "sl_hit"


def test_evaluate_exit_short_both_in_bar_prefers_sl():
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    trade = SimpleNamespace(side="SHORT", stop_loss=110.0, take_profit=90.0)
    candles = [_bar(t0, 85.0, 115.0)]
    r = evaluate_exit(trade, candles)
    assert r is not None
    assert r[0] == "sl_hit"


def test_evaluate_exit_no_levels_returns_none():
    trade = SimpleNamespace(side="LONG", stop_loss=None, take_profit=110.0)
    r = evaluate_exit(trade, [])
    assert r is None


def test_evaluate_exit_unknown_side_returns_none():
    trade = SimpleNamespace(side="WAIT", stop_loss=1.0, take_profit=2.0)
    r = evaluate_exit(trade, [_bar(dt.datetime.now(dt.timezone.utc), 0.5, 3.0)])
    assert r is None


@pytest.mark.parametrize(
    ("low", "high"),
    [(96.0, 104.0), (95.5, 104.5)],
)
def test_evaluate_exit_no_touch(low: float, high: float):
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    trade = SimpleNamespace(side="LONG", stop_loss=90.0, take_profit=110.0)
    candles = [_bar(t0, low, high)]
    assert evaluate_exit(trade, candles) is None
