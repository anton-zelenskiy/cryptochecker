from __future__ import annotations

import datetime as dt
from typing import Protocol


class _OHLCBar(Protocol):
    open_time_utc: dt.datetime
    high: float
    low: float


class _TradeExitInputs(Protocol):
    side: str
    stop_loss: float | None
    take_profit: float | None


def evaluate_exit(
    trade: _TradeExitInputs,
    candles_asc: list[_OHLCBar],
) -> tuple[str, float, dt.datetime] | None:
    sl = trade.stop_loss
    tp = trade.take_profit
    if sl is None or tp is None:
        return None
    if trade.side == "LONG":
        return _evaluate_long(sl=float(sl), tp=float(tp), candles_asc=candles_asc)
    if trade.side == "SHORT":
        return _evaluate_short(sl=float(sl), tp=float(tp), candles_asc=candles_asc)
    return None


def _evaluate_long(
    *,
    sl: float,
    tp: float,
    candles_asc: list[_OHLCBar],
) -> tuple[str, float, dt.datetime] | None:
    for c in candles_asc:
        low = float(c.low)
        high = float(c.high)
        sl_hit = low <= sl
        tp_hit = high >= tp
        if sl_hit and tp_hit:
            return "sl_hit", sl, c.open_time_utc
        if sl_hit:
            return "sl_hit", sl, c.open_time_utc
        if tp_hit:
            return "tp_hit", tp, c.open_time_utc
    return None


def _evaluate_short(
    *,
    sl: float,
    tp: float,
    candles_asc: list[_OHLCBar],
) -> tuple[str, float, dt.datetime] | None:
    for c in candles_asc:
        low = float(c.low)
        high = float(c.high)
        sl_hit = high >= sl
        tp_hit = low <= tp
        if sl_hit and tp_hit:
            return "sl_hit", sl, c.open_time_utc
        if sl_hit:
            return "sl_hit", sl, c.open_time_utc
        if tp_hit:
            return "tp_hit", tp, c.open_time_utc
    return None
