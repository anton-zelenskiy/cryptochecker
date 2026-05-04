from __future__ import annotations

import asyncio
import datetime as dt
import json
import time

import httpx
import websockets

from project.core.config import settings
from project.core.http_client import RateLimitPolicy, get_json
from project.core.rate_limit_provider import get_rate_limiter
from project.marketdata.api.ws_common import parse_orderbook_levels, parse_ts_ms, pick_support_wall
from project.marketdata.dto import NormalizedCandle, NormalizedMarket
from project.marketdata.timeframes import normalize_timeframe


KUCOIN_SPOT_PUSH_WS_URL = "wss://x-push-spot.kucoin.com"
KUCOIN_CANDLES_URL = "https://api.kucoin.com/api/v1/market/candles"


def _kucoin_symbol(market: NormalizedMarket) -> str:
    return f"{market.base_asset.upper()}-{market.quote_asset.upper()}"


def _kucoin_orderbook_topic(market: NormalizedMarket) -> str:
    return f"/spotMarket/level2Depth50:{_kucoin_symbol(market)}"


def _kucoin_candle_type(timeframe: str) -> str:
    tf = normalize_timeframe(timeframe).code
    return {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "1h": "1hour",
        "4h": "4hour",
        "1d": "1day",
    }[tf]


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
    topics = [_kucoin_orderbook_topic(m) for m in sub_markets]
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

            bids = parse_orderbook_levels(data.get("bids"))
            picked = pick_support_wall(bids)
            if not picked:
                done_syms.add(sym_key)
                continue

            wall_price, wall_qty, wall_notional, best_bid, median_qty = picked
            ts_ms = parse_ts_ms(data.get("timestamp")) or parse_ts_ms(data.get("ts"))
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


class KuCoinApi:
    source = "kucoin"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        api_passphrase: str | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.KUCOIN_API_KEY
        self._api_secret = api_secret if api_secret is not None else settings.KUCOIN_API_SECRET
        self._api_passphrase = api_passphrase if api_passphrase is not None else settings.KUCOIN_API_PASSPHRASE

    def _headers(self) -> dict[str, str] | None:
        if not self._api_key:
            return None
        headers: dict[str, str] = {"KC-API-KEY": self._api_key}
        if self._api_secret:
            headers["KC-API-SECRET"] = self._api_secret
        if self._api_passphrase:
            headers["KC-API-PASSPHRASE"] = self._api_passphrase
        return headers

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

        params = {
            "symbol": market.pair,
            "type": _kucoin_candle_type(tf_code),
            "startAt": int(start.timestamp()),
            "endAt": int(end.timestamp()),
        }

        rate_limiter = await get_rate_limiter()
        rate = RateLimitPolicy(key="ratelimit:kucoin:candles", limit=20, window_s=60)
        headers = self._headers()

        async with httpx.AsyncClient(timeout=45.0) as client:
            payload = await get_json(
                client,
                url=KUCOIN_CANDLES_URL,
                params=params,
                headers=headers,
                rate_limiter=rate_limiter,
                rate_limit=rate,
                max_attempts=10,
                start_delay_s=3.0,
                back_off=3,
            )

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []

        result: list[NormalizedCandle] = []
        for item in data:
            if not isinstance(item, list) or len(item) < 7:
                continue
            try:
                ts_s = int(item[0])
                open_ = float(item[1])
                close_ = float(item[2])
                high_ = float(item[3])
                low_ = float(item[4])
                volume_ = float(item[5])
                turnover_ = float(item[6])
            except Exception:
                continue

            t = dt.datetime.fromtimestamp(ts_s, tz=dt.timezone.utc)
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
        if limit is not None:
            result = result[-limit:]
        return result
