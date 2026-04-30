from __future__ import annotations

import datetime as dt

import structlog
import httpx

from project.marketdata.dto import NormalizedCandle, NormalizedMarket
from project.marketdata.providers.candles import CandleProvider
from project.marketdata.timeframes import normalize_timeframe
from project.core.http_client import RateLimitPolicy, get_json_with_retries
from project.core.rate_limit_provider import get_rate_limiter


logger = structlog.get_logger(__name__)

KUCOIN_CANDLES_URL = "https://api.kucoin.com/api/v1/market/candles"


def _kucoin_type(timeframe: str) -> str:
    tf = normalize_timeframe(timeframe).code
    return {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "1h": "1hour",
        "4h": "4hour",
        "1d": "1day",
    }[tf]


class KuCoinCandleProvider(CandleProvider):
    source = "kucoin"

    def __init__(self) -> None:
        pass

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
            "type": _kucoin_type(tf_code),
            "startAt": int(start.timestamp()),
            "endAt": int(end.timestamp()),
        }

        rate_limiter = await get_rate_limiter()
        rate = RateLimitPolicy(key="ratelimit:kucoin:candles", limit=20, window_s=60)

        async with httpx.AsyncClient(timeout=45.0) as client:
            payload = await get_json_with_retries(
                client,
                url=KUCOIN_CANDLES_URL,
                params=params,
                rate_limiter=rate_limiter,
                rate_limit=rate,
                max_attempts=3,
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

