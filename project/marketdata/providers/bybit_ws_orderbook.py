from __future__ import annotations

import asyncio
import datetime as dt
import json
import statistics
from collections.abc import AsyncIterator

import websockets

from project.marketdata.dto import NormalizedMarket


BYBIT_SPOT_WS_URL = "wss://stream.bybit.com/v5/public/spot"


def _orderbook_topic(market: NormalizedMarket) -> str:
    return f"orderbook.50.{market.base_asset.upper()}{market.quote_asset.upper()}"


async def _iter_messages(ws) -> AsyncIterator[dict]:
    # NOTE: keep this generator bounded so callers can enforce wall-clock limits.
    while True:
        raw = await ws.recv()
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        yield msg


def _parse_levels(levels: object) -> list[tuple[float, float]]:
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
    """
    Returns (wall_price, wall_qty, wall_notional, best_bid, median_bid_qty) or None.
    """
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


def _parse_ts_ms(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


async def collect_orderbook_walls_for_markets(
    markets: list[NormalizedMarket],
    *,
    duration_s: float = 20.0,
    max_markets: int = 10,
    extra_headers: dict[str, str] | None = None,
) -> list[dict]:
    if not markets:
        return []

    sub_markets = markets[:max_markets]
    topics = [_orderbook_topic(m) for m in sub_markets]
    markets_by_sym = {f"{m.base_asset.upper()}{m.quote_asset.upper()}": m for m in sub_markets}

    rows: list[dict] = []
    started = asyncio.get_running_loop().time()
    done_syms: set[str] = set()

    async with websockets.connect(
        BYBIT_SPOT_WS_URL,
        ping_interval=20,
        ping_timeout=20,
        additional_headers=extra_headers,
    ) as ws:
        await ws.send(json.dumps({"op": "subscribe", "args": topics}))

        # Bybit can be silent; don't block forever on recv().
        while True:
            if len(done_syms) >= len(sub_markets):
                break
            elapsed = asyncio.get_running_loop().time() - started
            if elapsed >= duration_s:
                break

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=min(1.0, max(0.01, duration_s - elapsed)))
            except asyncio.TimeoutError:
                continue

            try:
                msg = json.loads(raw)
            except Exception:
                continue

            topic = msg.get("topic")
            if not isinstance(topic, str) or not topic.startswith("orderbook.50."):
                continue

            sym_from_topic = topic.removeprefix("orderbook.50.")

            # MVP: use snapshot bids only (first snapshot is enough for a periodic probe).
            if str(msg.get("type", "")).lower() != "snapshot":
                continue

            data = msg.get("data")
            if not isinstance(data, dict):
                continue

            sym = data.get("s")
            if isinstance(sym, str) and sym:
                sym_key = sym.upper()
            else:
                sym_key = sym_from_topic.upper()

            if sym_key in done_syms:
                continue

            market = markets_by_sym.get(sym_key)
            if market is None:
                continue

            bids = _parse_levels(data.get("b"))
            picked = pick_support_wall(bids)
            if not picked:
                done_syms.add(sym_key)
                continue

            wall_price, wall_qty, wall_notional, best_bid, median_qty = picked
            ts_ms = _parse_ts_ms(msg.get("ts")) or _parse_ts_ms(msg.get("cts"))
            if ts_ms is None:
                bucket = dt.datetime.now(dt.timezone.utc)
            else:
                bucket = dt.datetime.fromtimestamp(ts_ms / 1000, tz=dt.timezone.utc)

            rows.append(
                {
                    "source": "bybit",
                    "base_asset": market.base_asset.upper(),
                    "quote_asset": market.quote_asset.upper(),
                    "bucket_time_utc": bucket,
                    "wall_price": float(wall_price),
                    "wall_qty": float(wall_qty),
                    "wall_notional_quote": float(wall_notional),
                    "best_bid": float(best_bid),
                    "median_bid_qty": float(median_qty),
                    "detected_at": dt.datetime.now(dt.timezone.utc),
                }
            )
            done_syms.add(sym_key)

    return rows
