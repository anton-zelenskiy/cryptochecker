from __future__ import annotations

import datetime as dt

import structlog

from project.core.run_in_executor import run_in_executor
from project.marketdata.dto import NormalizedCandle, NormalizedMarket
from project.marketdata.providers.candles import CandleProvider
from project.marketdata.timeframes import normalize_timeframe
from project.api.bybit import BybitMarketAPI


logger = structlog.get_logger(__name__)


class BybitCandleProvider(CandleProvider):
    source = "bybit"

    def __init__(self, *, api_key: str = "", api_secret: str = "") -> None:
        # For public klines, empty keys are OK for pybit in many environments.
        self._api = BybitMarketAPI(api_key=api_key, api_secret=api_secret)

    @run_in_executor
    def _fetch_sync(
        self,
        market: NormalizedMarket,
        timeframe: str,
        start: dt.datetime,
        end: dt.datetime,
    ) -> list[NormalizedCandle]:
        tf = normalize_timeframe(timeframe)
        # current wrapper uses 5m only and 3h window; keep best-effort by calling get_ohlc
        # until the new httpx-based implementation is added.
        candles = self._api.get_ohlc(currency_code=market.base_asset.lower())
        result: list[NormalizedCandle] = []
        for c in candles:
            t = c.datetime.astimezone(dt.timezone.utc)
            if start <= t <= end:
                result.append(
                    NormalizedCandle(
                        source=self.source,
                        market=market,
                        timeframe=tf.code,
                        open_time_utc=t,
                        open=float(c.open),
                        high=float(c.high),
                        low=float(c.low),
                        close=float(c.close),
                        volume_base=float(getattr(c, "volume", 0.0) or 0.0),
                        volume_quote=float(getattr(c, "turnover", 0.0) or 0.0),
                    )
                )
        return result

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
        candles = await self._fetch_sync(market, timeframe, start, end)
        candles.sort(key=lambda c: c.open_time_utc)
        if limit is not None:
            candles = candles[-limit:]
        return candles

