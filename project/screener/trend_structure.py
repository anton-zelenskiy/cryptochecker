from __future__ import annotations

import math

from project.screener.contracts import TrendBias, TrendSwingFeature


def _pivot_highs(highs: list[float], left: int = 2, right: int = 2) -> list[bool]:
    n = len(highs)
    out = [False] * n
    for i in range(left, n - right):
        window = highs[i - left : i + right + 1]
        if highs[i] == max(window) and window.count(highs[i]) == 1:
            out[i] = True
    return out


def _pivot_lows(lows: list[float], left: int = 2, right: int = 2) -> list[bool]:
    n = len(lows)
    out = [False] * n
    for i in range(left, n - right):
        window = lows[i - left : i + right + 1]
        if lows[i] == min(window) and window.count(lows[i]) == 1:
            out[i] = True
    return out


def _last_two_pivot_lows(lows: list[float]) -> tuple[float | None, float | None]:
    ph = _pivot_lows(lows)
    vals = [lows[i] for i in range(len(lows)) if ph[i]]
    if len(vals) >= 2:
        return vals[-2], vals[-1]
    if len(vals) == 1:
        return None, vals[-1]
    return None, None


def _last_two_pivot_highs(highs: list[float]) -> tuple[float | None, float | None]:
    ph = _pivot_highs(highs)
    vals = [highs[i] for i in range(len(highs)) if ph[i]]
    if len(vals) >= 2:
        return vals[-2], vals[-1]
    if len(vals) == 1:
        return None, vals[-1]
    return None, None


def log_close_slope(closes: list[float], window: int = 20) -> float | None:
    if len(closes) < window or window < 3:
        return None
    y = closes[-window:]
    xs = list(range(window))
    mean_x = sum(xs) / window
    mean_y = sum(math.log(max(c, 1e-12)) for c in y) / window
    num = sum((xs[i] - mean_x) * (math.log(max(y[i], 1e-12)) - mean_y) for i in range(window))
    den = sum((xs[i] - mean_x) ** 2 for i in range(window))
    if den == 0:
        return None
    return num / den


def compute_trend_swing_feature(
    *,
    timeframe: str,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    ema20: float | None,
    ema50: float | None,
    ema200: float | None,
) -> TrendSwingFeature:
    if len(closes) < 10:
        return TrendSwingFeature(timeframe=timeframe, bias="neutral")

    prev_l, last_l = _last_two_pivot_lows(lows)
    prev_h, last_h = _last_two_pivot_highs(highs)
    higher_lows = bool(prev_l and last_l and last_l > prev_l)
    lower_highs = bool(prev_h and last_h and last_h < prev_h)
    last_close = closes[-1]
    ema20_above_50 = bool(ema20 and ema50 and ema20 > ema50)
    close_above_200 = bool(ema200 and last_close > ema200)
    slope = log_close_slope(closes, window=min(20, len(closes)))

    score = 0
    if higher_lows:
        score += 1
    if ema20_above_50:
        score += 1
    if close_above_200:
        score += 1
    if slope and slope > 0:
        score += 1
    if lower_highs:
        score -= 1
    if not ema20_above_50 and ema20 and ema50:
        score -= 1
    if not close_above_200 and ema200:
        score -= 1
    if slope and slope < 0:
        score -= 1

    bias: TrendBias
    if score >= 2:
        bias = "bull"
    elif score <= -2:
        bias = "bear"
    else:
        bias = "neutral"

    return TrendSwingFeature(
        timeframe=timeframe,
        bias=bias,
        higher_lows=higher_lows if prev_l is not None else None,
        lower_highs=lower_highs if prev_h is not None else None,
        ema20_above_ema50=ema20_above_50 if ema20 and ema50 else None,
        close_above_ema200=close_above_200 if ema200 else None,
        log_close_slope_20=slope,
    )


def aggregate_bias(biases: list[TrendBias]) -> TrendBias:
    s = sum({"bull": 1, "bear": -1, "neutral": 0}.get(b, 0) for b in biases)
    if s >= 1:
        return "bull"
    if s <= -1:
        return "bear"
    return "neutral"
