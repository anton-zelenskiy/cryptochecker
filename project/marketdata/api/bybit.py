from __future__ import annotations
import structlog
import asyncio
import datetime as dt
import json

import httpx
import websockets

from project.core.config import settings
from project.core.http_client import RateLimitPolicy, get_json
from project.core.rate_limit_provider import get_rate_limiter
from project.marketdata.api.ws_common import parse_orderbook_levels, parse_ts_ms, pick_support_wall
from project.marketdata.dto import NormalizedCandle, NormalizedMarket
from project.marketdata.timeframes import normalize_timeframe


logger = structlog.get_logger(__name__)


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


def _chunked(items: list[str], *, chunk_size: int) -> list[list[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


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
    min_notional_quote_by_sym: dict[str, float] | None = None,
    qty_vs_median_multiplier_by_sym: dict[str, float] | None = None,
    default_min_notional_quote: float = 20_000.0,
    default_qty_vs_median_multiplier: float = 6.0,
) -> list[dict]:
    if not markets:
        return []

    def _drop_invalid_subscribe_symbols(msg: dict, markets_by_sym: dict[str, NormalizedMarket]) -> int:
        ret_msg = msg.get("ret_msg")
        if not isinstance(ret_msg, str) or "Invalid symbol" not in ret_msg:
            return 0

        lb = ret_msg.find("[")
        rb = ret_msg.find("]", lb + 1)
        if lb == -1 or rb == -1:
            return 0

        inner = ret_msg[lb + 1 : rb]
        if not inner:
            return 0

        dropped = 0
        for raw_topic in inner.split(","):
            topic = raw_topic.strip()
            if not topic.startswith("orderbook.50."):
                continue
            sym = topic.removeprefix("orderbook.50.").upper()
            if markets_by_sym.pop(sym, None) is not None:
                dropped += 1
        return dropped

    sub_markets = markets[:max_markets]
    topics = [_orderbook_topic(m) for m in sub_markets]
    markets_by_sym = {f"{m.base_asset.upper()}{m.quote_asset.upper()}": m for m in sub_markets}

    rows: list[dict] = []
    started = asyncio.get_running_loop().time()
    done_syms: set[str] = set()
    resubscribe_attempts = 0

    with structlog.contextvars.bound_contextvars(
        source="bybit",
        method="collect_orderbook_walls_for_markets",
    ):
        async with websockets.connect(
            BYBIT_SPOT_WS_URL,
            ping_interval=20,
            ping_timeout=20,
            additional_headers=extra_headers,
        ) as ws:
            # Bybit WS v5 enforces args length <= 10 per subscribe op.
            for args in _chunked(topics, chunk_size=10):
                logger.info("sending bybit subscribe batch", op="subscribe", args=len(args))
                await ws.send(json.dumps({"op": "subscribe", "args": args}))

            while True:
                if len(done_syms) >= len(markets_by_sym):
                    logger.info("orderbook walls collected for all markets", markets=len(sub_markets))
                    break
                elapsed = asyncio.get_running_loop().time() - started
                if elapsed >= duration_s:
                    logger.info(
                        "orderbook walls collect duration reached",
                        duration_s=duration_s,
                        markets=len(sub_markets),
                        done=len(done_syms),
                    )
                    break

                timeout = min(1.0, max(0.01, duration_s - elapsed))
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    logger.warning("WS timeout", timeout=timeout)
                    continue

                try:
                    msg = json.loads(raw)
                except Exception:
                    logger.error("failed to parse WS message", raw=raw)
                    continue

                # Handle subscribe errors (these messages often have no `topic`)
                if msg.get("op") == "subscribe" and msg.get("success") is False:
                    dropped = _drop_invalid_subscribe_symbols(msg, markets_by_sym)
                    if dropped > 0 and resubscribe_attempts < 3:
                        resubscribe_attempts += 1
                        done_syms = {s for s in done_syms if s in markets_by_sym}
                        topics = [f"orderbook.50.{sym}" for sym in markets_by_sym.keys()]
                        logger.warning(
                            "bybit subscribe had invalid symbols; retrying without them",
                            dropped=dropped,
                            remaining=len(topics),
                            attempt=resubscribe_attempts,
                            msg=msg,
                        )
                        for args in _chunked(topics, chunk_size=10):
                            logger.info("sending bybit subscribe batch", op="subscribe", args=len(args))
                            await ws.send(json.dumps({"op": "subscribe", "args": args}))
                        continue

                    logger.error("bybit subscribe failed", msg=msg)
                    break

                topic = msg.get("topic")
                if not isinstance(topic, str) or not topic.startswith("orderbook.50."):
                    # subscribe acks and other service messages don't have an orderbook topic
                    continue

                sym_from_topic = topic.removeprefix("orderbook.50.")

                msg_type = str(msg.get("type", "")).lower()
                if msg_type != "snapshot":
                    # Bybit sends frequent `delta` updates after the initial snapshot; we only need snapshots here.
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
                    logger.info("orderbook snapshot for untracked market", sym=sym_key, topic=topic)
                    continue

                bids = parse_orderbook_levels(data.get("b"))
                min_notional_quote = default_min_notional_quote
                if min_notional_quote_by_sym is not None:
                    min_notional_quote = float(min_notional_quote_by_sym.get(sym_key, min_notional_quote))
                qty_vs_median_multiplier = default_qty_vs_median_multiplier
                if qty_vs_median_multiplier_by_sym is not None:
                    qty_vs_median_multiplier = float(
                        qty_vs_median_multiplier_by_sym.get(sym_key, qty_vs_median_multiplier)
                    )
                picked = pick_support_wall(
                    bids,
                    min_notional_quote=min_notional_quote,
                    qty_vs_median_multiplier=qty_vs_median_multiplier,
                )
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

        logger.info("orderbook walls collected", rows=len(rows))

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

    def _drop_invalid_subscribe_symbols(msg: dict, markets_by_sym: dict[str, NormalizedMarket]) -> int:
        ret_msg = msg.get("ret_msg")
        if not isinstance(ret_msg, str) or "Invalid symbol" not in ret_msg:
            return 0

        lb = ret_msg.find("[")
        rb = ret_msg.find("]", lb + 1)
        if lb == -1 or rb == -1:
            return 0

        inner = ret_msg[lb + 1 : rb]
        if not inner:
            return 0

        dropped = 0
        for raw_topic in inner.split(","):
            topic = raw_topic.strip()
            if not topic.startswith("publicTrade."):
                continue
            sym = topic.removeprefix("publicTrade.").upper()
            if markets_by_sym.pop(sym, None) is not None:
                dropped += 1
        return dropped

    sub_markets = markets[:max_markets]
    topics = [_public_trade_topic(m) for m in sub_markets]
    markets_by_sym = {f"{m.base_asset.upper()}{m.quote_asset.upper()}": m for m in sub_markets}

    rows: list[dict] = []
    started = asyncio.get_running_loop().time()

    with structlog.contextvars.bound_contextvars(
        method="collect_trades_for_markets",
    ):
        async with websockets.connect(
            BYBIT_SPOT_WS_URL,
            ping_interval=20,
            ping_timeout=20,
            additional_headers=extra_headers,
        ) as ws:
            # Bybit WS v5 enforces args length <= 10 per subscribe op.
            for args in _chunked(topics, chunk_size=10):
                await ws.send(json.dumps({"op": "subscribe", "args": args}))

            while True:
                elapsed = asyncio.get_running_loop().time() - started
                if elapsed >= duration_s:
                    logger.info("market trades ingest duration reached", duration_s=duration_s)
                    break

                timeout = min(1.0, max(0.05, duration_s - elapsed))
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    logger.warning("WS timeout", timeout=timeout)
                    continue

                try:
                    msg = json.loads(raw)
                except Exception:
                    logger.error("failed to parse WS message", raw=raw)
                    continue

                # Handle subscribe errors (these messages often have no `topic`)
                if msg.get("op") == "subscribe" and msg.get("success") is False:
                    dropped = _drop_invalid_subscribe_symbols(msg, markets_by_sym)
                    if dropped:
                        logger.warning("bybit subscribe skipped invalid symbols", dropped=dropped, msg=msg)
                        continue
                    logger.error("bybit subscribe failed", msg=msg)
                    continue

                topic = msg.get("topic")
                if not isinstance(topic, str) or not topic.startswith("publicTrade."):
                    logger.warning("invalid topic", topic=topic)
                    continue

                data = msg.get("data")
                if not isinstance(data, list):
                    logger.warning("invalid data", data=data)
                    continue

                sym = topic.removeprefix("publicTrade.").upper()
                market = markets_by_sym.get(sym)
                if market is None:
                    logger.warning("market not found", sym=sym)
                    continue

                for item in data:
                    if not isinstance(item, dict):
                        logger.warning("invalid item", item=item)
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
        rate = RateLimitPolicy(key="ratelimit:bybit:kline", limit=200, window_s=60)
        headers = self._headers()

        async with httpx.AsyncClient(timeout=45.0) as client:
            payload = await get_json(
                client,
                url=BYBIT_KLINE_URL,
                params=params,
                headers=headers,
                rate_limiter=rate_limiter,
                rate_limit=rate,
                max_attempts=10,
                start_delay_s=3.0,
                back_off=3,
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
