from __future__ import annotations

import asyncio
import datetime as dt
import json
import time
from collections.abc import AsyncIterator

import websockets

from project.marketdata.dto import NormalizedMarket
from project.marketdata.providers.bybit_ws_orderbook import _parse_levels, _parse_ts_ms, pick_support_wall


KUCOIN_SPOT_PUSH_WS_URL = "wss://x-push-spot.kucoin.com"


def _kucoin_symbol(market: NormalizedMarket) -> str:
    return f"{market.base_asset.upper()}-{market.quote_asset.upper()}"


def _orderbook_topic(market: NormalizedMarket) -> str:
    return f"/spotMarket/level2Depth50:{_kucoin_symbol(market)}"


async def _iter_messages(ws) -> AsyncIterator[dict]:
    while True:
        raw = await ws.recv()
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        yield msg


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
    markets_by_sym = {_kucoin_symbol(m): m for m in sub_markets}

    rows: list[dict] = []
    started = asyncio.get_running_loop().time()
    done_syms: set[str] = set()

    async with websockets.connect(
        KUCOIN_SPOT_PUSH_WS_URL,
        ping_interval=20,
        ping_timeout=20,
        additional_headers=extra_headers,
    ) as ws:
        for topic in topics:
            await ws.send(
                json.dumps(
                    {
                        "id": int(time.time() * 1000),
                        "type": "subscribe",
                        "topic": topic,
                        "response": True,
                    }
                )
            )

        async for msg in _iter_messages(ws):
            if len(done_syms) >= len(sub_markets):
                break
            if asyncio.get_running_loop().time() - started >= duration_s:
                break

            if str(msg.get("type", "")).lower() != "message":
                continue

            topic = msg.get("topic")
            if not isinstance(topic, str) or not topic.startswith("/spotMarket/level2Depth50:"):
                continue

            sym = topic.removeprefix("/spotMarket/level2Depth50:")
            sym_key = sym.upper()
            if sym_key in done_syms:
                continue

            market = markets_by_sym.get(sym_key)
            if market is None:
                continue

            data = msg.get("data")
            if not isinstance(data, dict):
                continue

            bids = _parse_levels(data.get("bids"))
            picked = pick_support_wall(bids)
            if not picked:
                done_syms.add(sym_key)
                continue

            wall_price, wall_qty, wall_notional, best_bid, median_qty = picked
            ts_ms = _parse_ts_ms(data.get("timestamp")) or _parse_ts_ms(data.get("ts"))
            if ts_ms is None:
                bucket = dt.datetime.now(dt.timezone.utc)
            else:
                bucket = dt.datetime.fromtimestamp(ts_ms / 1000, tz=dt.timezone.utc)

            rows.append(
                {
                    "source": "kucoin",
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
