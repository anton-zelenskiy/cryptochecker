from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import structlog

from project.core.config import settings
from project.core.http_client import RateLimitPolicy, get_json
from project.core.rate_limit_provider import get_rate_limiter
from project.core.redis_async import get_redis
from project.screener.contracts import DerivativesContext


logger = structlog.get_logger(__name__)

BYBIT_BASE = "https://api.bybit.com"
TICKER_URL = f"{BYBIT_BASE}/v5/market/tickers"
OPEN_INTEREST_URL = f"{BYBIT_BASE}/v5/market/open-interest"
ACCOUNT_RATIO_URL = f"{BYBIT_BASE}/v5/market/account-ratio"


def _linear_symbol(base_asset: str, quote_asset: str) -> str:
    return f"{base_asset.upper()}{quote_asset.upper()}"


def _cache_key(symbol: str) -> str:
    return f"bybit:linear:derivatives:{symbol}"


def _parse_ticker_row(row: dict) -> tuple[float | None, float | None, float | None]:
    mark: float | None = None
    oi: float | None = None
    funding: float | None = None
    try:
        if row.get("markPrice") is not None:
            mark = float(row["markPrice"])
    except (TypeError, ValueError):
        pass
    try:
        if row.get("openInterest") is not None:
            oi = float(row["openInterest"])
    except (TypeError, ValueError):
        pass
    try:
        if row.get("fundingRate") is not None:
            funding = float(row["fundingRate"])
    except (TypeError, ValueError):
        pass
    return mark, oi, funding


def _oi_change_pct(rows: list[dict]) -> float | None:
    if len(rows) < 2:
        return None
    try:
        latest = float(rows[0].get("openInterest", 0))
        oldest = float(rows[-1].get("openInterest", 0))
    except (TypeError, ValueError):
        return None
    if oldest <= 0:
        return None
    return (latest - oldest) / oldest * 100.0


async def fetch_bybit_linear_derivatives_context(
    *,
    base_asset: str,
    quote_asset: str,
) -> DerivativesContext:
    symbol = _linear_symbol(base_asset, quote_asset)
    cache_key = _cache_key(symbol)
    ttl = int(settings.DERIVATIVES_CACHE_TTL_SEC)

    try:
        r = await get_redis()
        cached = await r.get(cache_key)
        if cached:
            data = json.loads(cached)
            return DerivativesContext.model_validate(data)
    except Exception as e:
        logger.warning("derivatives cache read failed", symbol=symbol, error=str(e))

    rate_limiter = await get_rate_limiter()
    rate = RateLimitPolicy(key="ratelimit:bybit:market", limit=120, window_s=60)
    funding_thr = float(settings.DERIVATIVES_FUNDING_CROWDED_THRESHOLD)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            ticker_payload = await get_json(
                client,
                url=TICKER_URL,
                params={"category": "linear", "symbol": symbol},
                rate_limiter=rate_limiter,
                rate_limit=rate,
            )
            oi_payload = await get_json(
                client,
                url=OPEN_INTEREST_URL,
                params={
                    "category": "linear",
                    "symbol": symbol,
                    "intervalTime": "1h",
                    "limit": 24,
                },
                rate_limiter=rate_limiter,
                rate_limit=rate,
            )
            ratio_payload = await get_json(
                client,
                url=ACCOUNT_RATIO_URL,
                params={"category": "linear", "symbol": symbol, "period": "1h", "limit": 1},
                rate_limiter=rate_limiter,
                rate_limit=rate,
            )
    except Exception as e:
        logger.info("bybit linear derivatives unavailable", symbol=symbol, error=str(e))
        return DerivativesContext(symbol=symbol, unavailable=True)

    if not isinstance(ticker_payload, dict) or ticker_payload.get("retCode") != 0:
        return DerivativesContext(symbol=symbol, unavailable=True)

    ticker_list = ticker_payload.get("result", {})
    ticker_list = ticker_list.get("list") if isinstance(ticker_list, dict) else None
    if not isinstance(ticker_list, list) or not ticker_list:
        return DerivativesContext(symbol=symbol, unavailable=True)

    mark, oi, funding = _parse_ticker_row(ticker_list[0])

    oi_rows: list[dict] = []
    if isinstance(oi_payload, dict) and oi_payload.get("retCode") == 0:
        result = oi_payload.get("result")
        if isinstance(result, dict) and isinstance(result.get("list"), list):
            oi_rows = [x for x in result["list"] if isinstance(x, dict)]

    oi_change = _oi_change_pct(oi_rows)
    oi_rising = oi_change is not None and oi_change > 2.0

    long_short_ratio: float | None = None
    if isinstance(ratio_payload, dict) and ratio_payload.get("retCode") == 0:
        result = ratio_payload.get("result")
        if isinstance(result, dict) and isinstance(result.get("list"), list) and result["list"]:
            row = result["list"][0]
            if isinstance(row, dict):
                try:
                    buy = float(row.get("buyRatio", 0))
                    sell = float(row.get("sellRatio", 0))
                    if sell > 0:
                        long_short_ratio = buy / sell
                except (TypeError, ValueError):
                    pass

    ctx = DerivativesContext(
        symbol=symbol,
        mark_price=mark,
        open_interest=oi,
        funding_rate=funding,
        oi_change_24h_pct=oi_change,
        long_short_ratio=long_short_ratio,
        funding_crowded_long=funding is not None and funding > funding_thr,
        funding_crowded_short=funding is not None and funding < -funding_thr,
        oi_rising=oi_rising,
        asof_time_utc=datetime.now(timezone.utc).isoformat(),
        unavailable=False,
    )

    try:
        r = await get_redis()
        await r.setex(cache_key, ttl, ctx.model_dump_json())
    except Exception as e:
        logger.warning("derivatives cache write failed", symbol=symbol, error=str(e))

    return ctx


def format_derivatives_telegram_line(ctx: DerivativesContext | None) -> str | None:
    if ctx is None or ctx.unavailable:
        return None
    parts: list[str] = []
    if ctx.funding_rate is not None:
        parts.append(f"Funding: {ctx.funding_rate * 100:+.3f}%")
    if ctx.oi_change_24h_pct is not None:
        parts.append(f"OI 24h: {ctx.oi_change_24h_pct:+.1f}%")
    if not parts:
        return None
    return " | ".join(parts)
