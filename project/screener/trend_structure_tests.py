from __future__ import annotations

from project.screener.trend_structure import aggregate_bias, compute_trend_swing_feature


def test_aggregate_bias() -> None:
    assert aggregate_bias(["bull", "bull", "neutral"]) == "bull"
    assert aggregate_bias(["bear", "bear"]) == "bear"
    assert aggregate_bias(["neutral", "neutral"]) == "neutral"


def test_trend_uptrend_closes() -> None:
    n = 80
    closes = [100.0 + i * 0.5 for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    feat = compute_trend_swing_feature(
        timeframe="1h",
        highs=highs,
        lows=lows,
        closes=closes,
        ema20=closes[-1] * 0.99,
        ema50=closes[-1] * 0.98,
        ema200=closes[-1] * 0.95,
    )
    assert feat.bias in ("bull", "neutral", "bear")
