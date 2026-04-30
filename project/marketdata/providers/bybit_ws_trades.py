from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import AsyncIterator

import structlog
import websockets

from project.marketdata.dto import NormalizedMarket


logger = structlog.get_logger(__name__)

BYBIT_SPOT_WS_URL = "wss://stream.bybit.com/v5/public/spot"


def _topic_for_market(market: NormalizedMarket) -> str:
    # Bybit uses e.g. publicTrade.BTCUSDT
    return f"publicTrade.{market.base_asset.upper()}{market.quote_asset.upper()}"


async def _iter_messages(ws) -> AsyncIterator[dict]:
    while True:
        raw = await ws.recv()
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        yield msg


def _parse_trade_item(item: dict, *, market: NormalizedMarket) -> dict | None:
    # Example keys observed in Bybit v5:
    # { "T": 167..., "s": "BTCUSDT", "S": "Buy", "v": "0.001", "p": "60000", "i": "12345" }
    trade_id = str(item.get("i") or item.get("tradeId") or "")
    if not trade_id:
        return None

    side_raw = str(item.get("S") or item.get("side") or "").lower()
    side = "buy" if side_raw in {"buy", "b"} else "sell"

    try:
        price = float(item.get("p") or item.get("price"))
        qty = float(item.get("v") or item.get("size") or item.get("qty"))
    except Exception:
        return None

    t_ms = item.get("T") or item.get("ts") or item.get("timestamp")
    try:
        trade_time = dt.datetime.fromtimestamp(int(t_ms) / 1000, tz=dt.timezone.utc)
    except Exception:
        trade_time = dt.datetime.now(dt.timezone.utc)

    return {
        "source": "bybit",
        "base_asset": market.base_asset.upper(),
        "quote_asset": market.quote_asset.upper(),
        "trade_id": trade_id,
        "side": side,
        "price": price,
        "qty": qty,
        "notional_quote": price * qty,
        "trade_time_utc": trade_time,
    }


async def collect_trades_for_markets(
    markets: list[NormalizedMarket],
    *,
    duration_s: float = 20.0,
    max_markets: int = 20,
    extra_headers: dict[str, str] | None = None,
) -> list[dict]:
    if not markets:
        return []

    sub_markets = markets[:max_markets]
    topics = [_topic_for_market(m) for m in sub_markets]

    rows: list[dict] = []
    started = asyncio.get_running_loop().time()

    async with websockets.connect(
        BYBIT_SPOT_WS_URL,
        ping_interval=20,
        ping_timeout=20,
        additional_headers=extra_headers,
    ) as ws:
        await ws.send(json.dumps({"op": "subscribe", "args": topics}))

        async for msg in _iter_messages(ws):
            if asyncio.get_running_loop().time() - started >= duration_s:
                break

            topic = msg.get("topic")
            if not isinstance(topic, str) or not topic.startswith("publicTrade."):
                continue

            data = msg.get("data")
            if not isinstance(data, list):
                continue

            # match topic to market
            sym = topic.removeprefix("publicTrade.")
            market = next(
                (m for m in sub_markets if f"{m.base_asset.upper()}{m.quote_asset.upper()}" == sym),
                None,
            )
            if market is None:
                continue

            for item in data:
                if not isinstance(item, dict):
                    continue
                row = _parse_trade_item(item, market=market)
                if row:
                    rows.append(row)

    return rows

