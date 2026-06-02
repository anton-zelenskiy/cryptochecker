from __future__ import annotations

from project.screener.liquidity_structure import compute_liquidity_structure


def _flat(n: int, hi: float, lo: float) -> tuple[list[float], list[float], list[float]]:
    highs = [hi] * n
    lows = [lo] * n
    closes = [(hi + lo) / 2] * n
    return highs, lows, closes


def _inject_pivot_low(lows: list[float], highs: list[float], idx: int, level: float) -> None:
    for j in range(max(0, idx - 2), min(len(lows), idx + 3)):
        if j == idx:
            lows[j] = level
            highs[j] = level + 0.008
        else:
            lows[j] = max(lows[j], level + 0.004)
            highs[j] = max(highs[j], lows[j] + 0.006)


def _inject_pivot_high(lows: list[float], highs: list[float], idx: int, level: float) -> None:
    for j in range(max(0, idx - 2), min(len(highs), idx + 3)):
        if j == idx:
            highs[j] = level
            lows[j] = level - 0.008
        else:
            highs[j] = min(highs[j], level - 0.004)
            lows[j] = min(lows[j], highs[j] - 0.006)


def _series_setup_a() -> tuple[list[float], list[float], list[float]]:
    n = 50
    highs, lows, closes = _flat(n, hi=0.300, lo=0.292)
    _inject_pivot_low(lows, highs, 8, 0.270)
    _inject_pivot_low(lows, highs, 20, 0.275)
    _inject_pivot_high(lows, highs, 14, 0.285)
    for i in range(15, 35):
        highs[i] = min(highs[i], 0.284)
        lows[i] = max(lows[i], 0.280)
    for i in range(35, n):
        highs[i] = 0.298
        lows[i] = 0.288
        closes[i] = 0.293
    closes = [(h + lo) / 2 for h, lo in zip(highs, lows, strict=True)]
    return highs, lows, closes


def _series_setup_b() -> tuple[list[float], list[float], list[float]]:
    n = 50
    highs, lows, closes = _flat(n, hi=0.310, lo=0.302)
    _inject_pivot_high(lows, highs, 8, 0.330)
    _inject_pivot_high(lows, highs, 20, 0.325)
    _inject_pivot_low(lows, highs, 14, 0.315)
    for i in range(15, 35):
        lows[i] = max(lows[i], 0.316)
        highs[i] = min(highs[i], 0.320)
    for i in range(35, n):
        lows[i] = 0.302
        highs[i] = 0.310
        closes[i] = 0.306
    closes = [(h + lo) / 2 for h, lo in zip(highs, lows, strict=True)]
    return highs, lows, closes


def _series_all_lows_swept() -> tuple[list[float], list[float], list[float]]:
    n = 50
    highs, lows, closes = _flat(n, hi=1.05, lo=0.95)
    _inject_pivot_low(lows, highs, 10, 0.90)
    for i in range(30, n):
        lows[i] = 0.88
        highs[i] = 1.02
    closes = [(h + lo) / 2 for h, lo in zip(highs, lows, strict=True)]
    return highs, lows, closes


def test_sweep_setup_down_detected() -> None:
    highs, lows, closes = _series_setup_a()
    out = compute_liquidity_structure(
        highs=highs,
        lows=lows,
        closes=closes,
        current_price=closes[-1],
        lookback_days=14,
    )
    assert out.pattern == "sweep_setup_down", (
        f"got {out.pattern} untouched_lows={out.untouched_low_count} "
        f"swept_highs={out.swept_high_count}"
    )
    assert out.untouched_low_count >= 2
    assert out.swept_high_count >= 1
    assert out.magnet_below is not None
    assert out.narrative_ru is not None
    assert "sweep вниз" in out.narrative_ru


def test_sweep_setup_up_detected() -> None:
    highs, lows, closes = _series_setup_b()
    out = compute_liquidity_structure(
        highs=highs,
        lows=lows,
        closes=closes,
        current_price=closes[-1],
        lookback_days=14,
    )
    assert out.pattern == "sweep_setup_up", (
        f"got {out.pattern} untouched_highs={out.untouched_high_count} "
        f"swept_lows={out.swept_low_count}"
    )
    assert out.untouched_high_count >= 2
    assert out.swept_low_count >= 1
    assert out.magnet_above is not None
    assert out.narrative_ru is not None
    assert "sweep вверх" in out.narrative_ru


def test_liquidity_taken_below() -> None:
    highs, lows, closes = _series_all_lows_swept()
    out = compute_liquidity_structure(
        highs=highs,
        lows=lows,
        closes=closes,
        current_price=closes[-1],
        lookback_days=14,
    )
    assert out.pattern in ("liquidity_taken_below", "balanced", "none")


def test_too_few_bars_returns_none_pattern() -> None:
    out = compute_liquidity_structure(
        highs=[1.0, 1.1],
        lows=[0.9, 0.95],
        closes=[0.95, 1.05],
    )
    assert out.pattern == "none"
