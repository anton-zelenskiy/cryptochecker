from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import websockets

from project.core.config import settings
from project.core.http_client import RateLimitPolicy, get_json
from project.core.rate_limit_provider import get_rate_limiter
from project.marketdata.api.ws_common import parse_orderbook_levels, parse_ts_ms, pick_support_wall
from project.marketdata.dto import NormalizedCandle, NormalizedMarket
from project.marketdata.timeframes import normalize_timeframe


BYBIT_SPOT_WS_URL = "wss://stream.bybit.com/v5/public/spot"
BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"


def _bybit_interval(timeframe: str) -> str:
    tf = normalize_timeframe(timeframe).code
    return {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1d": "D",
    }[tf]


def _orderbook_topic(market: NormalizedMarket) -> str:
    return f"orderbook.50.{market.base_asset.upper()}{market.quote_asset.upper()}"


def _public_trade_topic(market: NormalizedMarket) -> str:
    return f"publicTrade.{market.base_asset.upper()}{market.quote_asset.upper()}"


async def _iter_ws_messages(ws: Any) -> AsyncIterator[dict]:
    while True:
        raw = await ws.recv()
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        yield msg


def parse_public_trade_item(item: dict, *, market: NormalizedMarket) -> dict | None:
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

            bids = parse_orderbook_levels(data.get("b"))
            picked = pick_support_wall(bids)
            if not picked:
                done_syms.add(sym_key)
                continue

            wall_price, wall_qty, wall_notional, best_bid, median_qty = picked
            ts_ms = parse_ts_ms(msg.get("ts")) or parse_ts_ms(msg.get("cts"))
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
    topics = [_public_trade_topic(m) for m in sub_markets]

    rows: list[dict] = []
    started = asyncio.get_running_loop().time()

    async with websockets.connect(
        BYBIT_SPOT_WS_URL,
        ping_interval=20,
        ping_timeout=20,
        additional_headers=extra_headers,
    ) as ws:
        await ws.send(json.dumps({"op": "subscribe", "args": topics}))

        async for msg in _iter_ws_messages(ws):
            if asyncio.get_running_loop().time() - started >= duration_s:
                break

            topic = msg.get("topic")
            if not isinstance(topic, str) or not topic.startswith("publicTrade."):
                continue

            data = msg.get("data")
            if not isinstance(data, list):
                continue

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
                row = parse_public_trade_item(item, market=market)
                if row:
                    rows.append(row)

    return rows


class BybitApi:
    source = "bybit"

    def __init__(self, *, api_key: str | None = None, api_secret: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.BYBIT_API_KEY
        self._api_secret = api_secret if api_secret is not None else settings.BYBIT_API_SECRET

    def _headers(self) -> dict[str, str] | None:
        if not self._api_key:
            return None
        _ = self._api_secret
        return {"X-BAPI-API-KEY": self._api_key}

    async def fetch_ohlcv(
        self,
        market: NormalizedMarket,
        timeframe: str,
        start: dt.datetime,
        end: dt.datetime,
        *,
        limit: int | None = None,
    ) -> list[NormalizedCandle]:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end must be timezone-aware (UTC)")

        tf_code = normalize_timeframe(timeframe).code
        interval = _bybit_interval(tf_code)
        symbol = f"{market.base_asset.upper()}{market.quote_asset.upper()}"

        params = {
            "category": "spot",
            "symbol": symbol,
            "interval": interval,
            "start": int(start.timestamp() * 1000),
            "end": int(end.timestamp() * 1000),
        }
        if limit is not None:
            params["limit"] = int(limit)

        rate_limiter = await get_rate_limiter()
        rate = RateLimitPolicy(key="ratelimit:bybit:kline", limit=20, window_s=60)
        headers = self._headers()

        async with httpx.AsyncClient(timeout=45.0) as client:
            payload = await get_json(
                client,
                url=BYBIT_KLINE_URL,
                params=params,
                headers=headers,
                rate_limiter=rate_limiter,
                rate_limit=rate,
                max_attempts=3,
            )

        result_obj = payload.get("result") if isinstance(payload, dict) else None
        data = result_obj.get("list") if isinstance(result_obj, dict) else None
        if not isinstance(data, list):
            return []

        result: list[NormalizedCandle] = []
        for item in data:
            if not isinstance(item, list) or len(item) < 7:
                continue
            try:
                ts_ms = int(item[0])
                open_ = float(item[1])
                high_ = float(item[2])
                low_ = float(item[3])
                close_ = float(item[4])
                volume_ = float(item[5])
                turnover_ = float(item[6])
            except Exception:
                continue

            t = dt.datetime.fromtimestamp(ts_ms / 1000, tz=dt.timezone.utc)
            if not (start <= t <= end):
                continue

            result.append(
                NormalizedCandle(
                    source=self.source,
                    market=market,
                    timeframe=tf_code,
                    open_time_utc=t,
                    open=open_,
                    high=high_,
                    low=low_,
                    close=close_,
                    volume_base=volume_,
                    volume_quote=turnover_,
                )
            )

        result.sort(key=lambda c: c.open_time_utc)
        return result
