from __future__ import annotations

import statistics


def parse_orderbook_levels(levels: object) -> list[tuple[float, float]]:
    if not isinstance(levels, list):
        return []
    out: list[tuple[float, float]] = []
    for lvl in levels:
        if not isinstance(lvl, (list, tuple)) or len(lvl) < 2:
            continue
        try:
            price = float(lvl[0])
            qty = float(lvl[1])
        except Exception:
            continue
        out.append((price, qty))
    return out


def pick_support_wall(
    bids: list[tuple[float, float]],
    *,
    min_notional_quote: float = 200_000.0,
    qty_vs_median_multiplier: float = 10.0,
    top_n: int = 50,
) -> tuple[float, float, float, float, float] | None:
    bids = sorted(bids, key=lambda x: x[0], reverse=True)[:top_n]
    if not bids:
        return None

    best_bid = float(bids[0][0])
    bid_qtys = [q for _, q in bids if q > 0]
    if not bid_qtys:
        return None

    median_qty = float(statistics.median(bid_qtys))

    best: tuple[float, float, float] | None = None
    for price, qty in bids:
        notional = price * qty
        if notional < min_notional_quote:
            continue
        if median_qty > 0 and qty < qty_vs_median_multiplier * median_qty:
            continue
        if best is None or notional > best[2]:
            best = (price, qty, notional)

    if best is None:
        return None
    wall_price, wall_qty, wall_notional = best
    return wall_price, wall_qty, wall_notional, best_bid, median_qty


def parse_ts_ms(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None
