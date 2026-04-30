from __future__ import annotations

import datetime as dt

import structlog
import httpx

from project.core.config import settings
from project.marketdata.dto import NormalizedCandle, NormalizedMarket
from project.marketdata.providers.candles import CandleProvider
from project.marketdata.timeframes import normalize_timeframe
from project.core.http_client import RateLimitPolicy, get_json_with_retries
from project.core.rate_limit_provider import get_rate_limiter


logger = structlog.get_logger(__name__)

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


class BybitCandleProvider(CandleProvider):
    source = "bybit"

    def __init__(self, *, api_key: str | None = None, api_secret: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.BYBIT_API_KEY
        self._api_secret = api_secret if api_secret is not None else settings.BYBIT_API_SECRET

    def _headers(self) -> dict[str, str] | None:
        if not self._api_key:
            return None
        # Public market endpoints should not require signing; avoid sending secrets on unsigned requests.
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
            payload = await get_json_with_retries(
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

