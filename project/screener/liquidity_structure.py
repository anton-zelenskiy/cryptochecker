from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from project.core.config import settings
from project.screener.contracts import LiquidityStructureComputed, SwingLevel
from project.screener.trend_structure import _pivot_highs, _pivot_lows

LiquidityPattern = Literal[
    "sweep_setup_down",
    "sweep_setup_up",
    "balanced",
    "liquidity_taken_below",
    "liquidity_taken_above",
    "none",
]

MIN_UNTOUCHED_SWINGS = 2
MIN_SWEPT_OPPOSITE = 1
RECENT_SWEEP_BARS = 18
PIVOT_LEFT = 2
PIVOT_RIGHT = 2


@dataclass(frozen=True)
class _PivotLow:
    index: int
    price: float


@dataclass(frozen=True)
class _PivotHigh:
    index: int
    price: float


def _sweep_tolerance() -> float:
    return float(settings.LIQUIDITY_SWEEP_TOLERANCE_PCT)


def _leverages() -> list[int]:
    raw = str(settings.LIQUIDATION_LEVERAGES)
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            lev = int(part)
        except ValueError:
            continue
        if lev > 1:
            out.append(lev)
    return out or [5, 10]


def _is_low_untouched(*, pivot_index: int, level: float, lows: list[float], tolerance: float) -> bool:
    floor = level * (1.0 - tolerance)
    for j in range(pivot_index + 1, len(lows)):
        if lows[j] < floor:
            return False
    return True


def _is_low_swept(*, pivot_index: int, level: float, lows: list[float], tolerance: float) -> bool:
    return not _is_low_untouched(
        pivot_index=pivot_index, level=level, lows=lows, tolerance=tolerance
    )


def _is_high_untouched(*, pivot_index: int, level: float, highs: list[float], tolerance: float) -> bool:
    ceiling = level * (1.0 + tolerance)
    for j in range(pivot_index + 1, len(highs)):
        if highs[j] > ceiling:
            return False
    return True


def _is_high_swept(*, pivot_index: int, level: float, highs: list[float], tolerance: float) -> bool:
    return not _is_high_untouched(
        pivot_index=pivot_index, level=level, highs=highs, tolerance=tolerance
    )


def _first_sweep_bar_low(*, pivot_index: int, level: float, lows: list[float], tolerance: float) -> int | None:
    floor = level * (1.0 - tolerance)
    for j in range(pivot_index + 1, len(lows)):
        if lows[j] < floor:
            return j
    return None


def _first_sweep_bar_high(*, pivot_index: int, level: float, highs: list[float], tolerance: float) -> int | None:
    ceiling = level * (1.0 + tolerance)
    for j in range(pivot_index + 1, len(highs)):
        if highs[j] > ceiling:
            return j
    return None


def _cluster_nearest_level(
    prices: list[float],
    *,
    current_price: float,
    cluster_pct: float,
    below: bool,
) -> float | None:
    if not prices:
        return None
    sorted_prices = sorted(prices, reverse=below)
    bands: list[list[float]] = []
    for p in sorted_prices:
        if below and p >= current_price:
            continue
        if not below and p <= current_price:
            continue
        placed = False
        for band in bands:
            anchor = band[0]
            if abs(p - anchor) / max(anchor, 1e-12) <= cluster_pct:
                band.append(p)
                placed = True
                break
        if not placed:
            bands.append([p])
    if not bands:
        return None
    best = max(bands, key=lambda b: (len(b), -min(abs(current_price - min(b)), abs(current_price - max(b)))))
    return sum(best) / len(best)


def _distance_pct(from_price: float, to_price: float) -> float:
    if from_price <= 0:
        return 0.0
    return (to_price - from_price) / from_price * 100.0


def _is_ascending(prices: list[float]) -> bool:
    if len(prices) < 2:
        return False
    return all(prices[i] < prices[i + 1] for i in range(len(prices) - 1))


def _is_descending(prices: list[float]) -> bool:
    if len(prices) < 2:
        return False
    return all(prices[i] > prices[i + 1] for i in range(len(prices) - 1))


def _liq_below_entry(entry: float, leverage: int) -> float:
    return entry * (1.0 - 1.0 / leverage)


def _liq_above_entry(entry: float, leverage: int) -> float:
    return entry * (1.0 + 1.0 / leverage)


def _format_level(price: float) -> str:
    return f"{price:g}"


def _build_narrative(
    *,
    pattern: LiquidityPattern,
    level: float | None,
    lookback_days: int,
) -> str | None:
    if pattern == "sweep_setup_down" and level is not None:
        return (
            f"4h ({lookback_days}д): минимумы не снимались, максимумы пробивались — "
            f"лонгисты в комфорте, шорты выбиты; вероятен sweep вниз к ликвидности ~{_format_level(level)}"
        )
    if pattern == "sweep_setup_up" and level is not None:
        return (
            f"4h ({lookback_days}д): максимумы не снимались, минимумы пробивались — "
            f"шорты в комфорте, лонги выбиты; вероятен sweep вверх к ликвидности ~{_format_level(level)}"
        )
    return None


def compute_liquidity_structure(
    *,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    current_price: float | None = None,
    timeframe: str | None = None,
    lookback_days: int | None = None,
) -> LiquidityStructureComputed:
    tf = timeframe or settings.LIQUIDITY_STRUCTURE_TIMEFRAME
    lb_days = lookback_days if lookback_days is not None else settings.LIQUIDITY_STRUCTURE_LOOKBACK_DAYS
    tolerance = _sweep_tolerance()
    cluster_pct = float(settings.LIQUIDITY_CLUSTER_PCT)
    max_dist_pct = float(settings.LIQUIDITY_MAGNET_MAX_DISTANCE_PCT)

    n = len(closes)
    if n < PIVOT_LEFT + PIVOT_RIGHT + 5:
        return LiquidityStructureComputed(timeframe=tf, lookback_days=lb_days, pattern="none")

    price = current_price if current_price is not None else closes[-1]
    bars_per_day = 6 if tf == "4h" else 24
    lookback_bars = min(n, max(20, lb_days * bars_per_day))
    start = n - lookback_bars
    h = highs[start:]
    lo = lows[start:]
    offset = start

    pivot_low_mask = _pivot_lows(lo, left=PIVOT_LEFT, right=PIVOT_RIGHT)
    pivot_high_mask = _pivot_highs(h, left=PIVOT_LEFT, right=PIVOT_RIGHT)

    pivot_lows: list[_PivotLow] = [
        _PivotLow(index=i + offset, price=lo[i]) for i in range(len(lo)) if pivot_low_mask[i]
    ]
    pivot_highs: list[_PivotHigh] = [
        _PivotHigh(index=i + offset, price=h[i]) for i in range(len(h)) if pivot_high_mask[i]
    ]

    untouched_lows: list[SwingLevel] = []
    swept_lows: list[SwingLevel] = []
    for pl in pivot_lows:
        local_i = pl.index - offset
        level = SwingLevel(price=pl.price, bar_index=pl.index)
        if _is_low_untouched(pivot_index=local_i, level=pl.price, lows=lo, tolerance=tolerance):
            untouched_lows.append(level)
        elif _is_low_swept(pivot_index=local_i, level=pl.price, lows=lo, tolerance=tolerance):
            swept_lows.append(level)

    untouched_highs: list[SwingLevel] = []
    swept_highs: list[SwingLevel] = []
    recent_swept_high_count = 0
    recent_swept_low_count = 0
    recent_start = max(0, len(h) - RECENT_SWEEP_BARS)

    for ph in pivot_highs:
        local_i = ph.index - offset
        level = SwingLevel(price=ph.price, bar_index=ph.index)
        if _is_high_untouched(pivot_index=local_i, level=ph.price, highs=h, tolerance=tolerance):
            untouched_highs.append(level)
        elif _is_high_swept(pivot_index=local_i, level=ph.price, highs=h, tolerance=tolerance):
            swept_highs.append(level)
            sweep_bar = _first_sweep_bar_high(
                pivot_index=local_i, level=ph.price, highs=h, tolerance=tolerance
            )
            if sweep_bar is not None and sweep_bar >= recent_start:
                recent_swept_high_count += 1

    for pl in pivot_lows:
        local_i = pl.index - offset
        if _is_low_swept(pivot_index=local_i, level=pl.price, lows=lo, tolerance=tolerance):
            sweep_bar = _first_sweep_bar_low(
                pivot_index=local_i, level=pl.price, lows=lo, tolerance=tolerance
            )
            if sweep_bar is not None and sweep_bar >= recent_start:
                recent_swept_low_count += 1

    untouched_low_prices = [s.price for s in untouched_lows]
    untouched_high_prices = [s.price for s in untouched_highs]

    liquidity_line_low = _cluster_nearest_level(
        untouched_low_prices,
        current_price=price,
        cluster_pct=cluster_pct,
        below=True,
    )
    liquidity_line_high = _cluster_nearest_level(
        untouched_high_prices,
        current_price=price,
        cluster_pct=cluster_pct,
        below=False,
    )

    magnet_below = liquidity_line_low
    magnet_above = liquidity_line_high

    dist_below: float | None = None
    dist_above: float | None = None
    if magnet_below is not None:
        dist_below = _distance_pct(price, magnet_below)
        if abs(dist_below) > max_dist_pct * 100.0:
            magnet_below = None
            dist_below = None
    if magnet_above is not None:
        dist_above = _distance_pct(price, magnet_above)
        if abs(dist_above) > max_dist_pct * 100.0:
            magnet_above = None
            dist_above = None

    recent_untouched_lows = [s for s in untouched_lows if s.bar_index >= offset + recent_start - 1]
    recent_untouched_highs = [s for s in untouched_highs if s.bar_index >= offset + recent_start - 1]

    low_prices_for_pattern = (
        [s.price for s in recent_untouched_lows] if recent_untouched_lows else untouched_low_prices
    )
    high_prices_for_pattern = (
        [s.price for s in recent_untouched_highs]
        if recent_untouched_highs
        else untouched_high_prices
    )

    rising_lows = _is_ascending(sorted(low_prices_for_pattern)[-MIN_UNTOUCHED_SWINGS:])
    falling_highs = _is_descending(sorted(high_prices_for_pattern, reverse=True)[-MIN_UNTOUCHED_SWINGS:])

    total_lows = len(pivot_lows)
    total_highs = len(pivot_highs)
    swept_low_ratio = len(swept_lows) / total_lows if total_lows else 0.0
    swept_high_ratio = len(swept_highs) / total_highs if total_highs else 0.0

    pattern: LiquidityPattern = "none"

    if (
        len(untouched_lows) >= MIN_UNTOUCHED_SWINGS
        and recent_swept_high_count >= MIN_SWEPT_OPPOSITE
        and liquidity_line_low is not None
        and price > liquidity_line_low
        and (rising_lows or len(untouched_lows) >= MIN_UNTOUCHED_SWINGS)
    ):
        pattern = "sweep_setup_down"
    elif (
        len(untouched_highs) >= MIN_UNTOUCHED_SWINGS
        and recent_swept_low_count >= MIN_SWEPT_OPPOSITE
        and liquidity_line_high is not None
        and price < liquidity_line_high
        and (falling_highs or len(untouched_highs) >= MIN_UNTOUCHED_SWINGS)
    ):
        pattern = "sweep_setup_up"
    elif total_lows >= 2 and swept_low_ratio >= 0.7 and len(untouched_lows) == 0:
        pattern = "liquidity_taken_below"
    elif total_highs >= 2 and swept_high_ratio >= 0.7 and len(untouched_highs) == 0:
        pattern = "liquidity_taken_above"
    elif recent_swept_high_count >= 1 and recent_swept_low_count >= 1:
        pattern = "balanced"
    elif len(untouched_lows) == 0 and len(untouched_highs) == 0 and (
        swept_low_ratio > 0 or swept_high_ratio > 0
    ):
        pattern = "balanced"

    levs = _leverages()
    liq_5x_below: float | None = None
    liq_10x_below: float | None = None
    liq_5x_above: float | None = None
    liq_10x_above: float | None = None
    if liquidity_line_low is not None:
        for lev in levs:
            val = _liq_below_entry(liquidity_line_low, lev)
            if lev == 5:
                liq_5x_below = val
            elif lev == 10:
                liq_10x_below = val
    if liquidity_line_high is not None:
        for lev in levs:
            val = _liq_above_entry(liquidity_line_high, lev)
            if lev == 5:
                liq_5x_above = val
            elif lev == 10:
                liq_10x_above = val

    narrative_level = liquidity_line_low if pattern == "sweep_setup_down" else liquidity_line_high
    narrative_ru = _build_narrative(
        pattern=pattern,
        level=narrative_level,
        lookback_days=lb_days,
    )

    return LiquidityStructureComputed(
        timeframe=tf,
        lookback_days=lb_days,
        pattern=pattern,
        untouched_low_count=len(untouched_lows),
        untouched_high_count=len(untouched_highs),
        swept_high_count=len(swept_highs),
        swept_low_count=len(swept_lows),
        liquidity_line_low=liquidity_line_low,
        liquidity_line_high=liquidity_line_high,
        magnet_below=magnet_below,
        magnet_above=magnet_above,
        distance_pct_below=dist_below,
        distance_pct_above=dist_above,
        liq_5x_below=liq_5x_below,
        liq_10x_below=liq_10x_below,
        liq_5x_above=liq_5x_above,
        liq_10x_above=liq_10x_above,
        narrative_ru=narrative_ru,
        untouched_lows=untouched_lows[:5],
        untouched_highs=untouched_highs[:5],
        swept_highs=swept_highs[:5],
        swept_lows=swept_lows[:5],
    )


def format_liquidity_telegram_lines(
    *,
    structure: LiquidityStructureComputed | None,
    derivatives_line: str | None = None,
) -> list[str]:
    if structure is None:
        return []
    lines: list[str] = []
    if structure.narrative_ru:
        lines.append(structure.narrative_ru)
    elif structure.pattern == "sweep_setup_down" and structure.magnet_below is not None:
        dist = structure.distance_pct_below
        dist_s = f" ({dist:+.1f}%)" if dist is not None else ""
        lines.append(
            f"4h ({structure.lookback_days}д): минимумы не снимались — ликвидность ↓ "
            f"{structure.magnet_below:g}{dist_s}\n"
            "         максимумы пробивались → возможен sweep вниз"
        )
    elif structure.pattern == "sweep_setup_up" and structure.magnet_above is not None:
        dist = structure.distance_pct_above
        dist_s = f" ({dist:+.1f}%)" if dist is not None else ""
        lines.append(
            f"4h ({structure.lookback_days}д): максимумы не снимались — ликвидность ↑ "
            f"{structure.magnet_above:g}{dist_s}\n"
            "         минимумы пробивались → возможен sweep вверх"
        )
    if derivatives_line:
        lines.append(derivatives_line)
    return lines
