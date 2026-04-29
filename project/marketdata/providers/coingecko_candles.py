from __future__ import annotations

import datetime as dt

import structlog

from project.core.run_in_executor import run_in_executor
from project.marketdata.dto import NormalizedCandle, NormalizedMarket
from project.marketdata.providers.candles import CandleProvider
from project.api.coingecko import CoingeckoMarketAPI
from project.marketdata.timeframes import normalize_timeframe


logger = structlog.get_logger(__name__)


class CoinGeckoCandleProvider(CandleProvider):
    source = "coingecko"

    def __init__(self) -> None:
        self._api = CoingeckoMarketAPI()

    @run_in_executor
    def _fetch_sync(self, base_asset: str) -> list[NormalizedCandle]:
        # CoinGecko OHLC endpoint in current wrapper is day-based and doesn't expose volume.
        candles = self._api.get_ohlc(currency_code=base_asset.lower())
        market = NormalizedMarket(base_asset=base_asset.upper(), quote_asset="USD")
        result: list[NormalizedCandle] = []
        for c in candles:
            t = c.datetime
            t_utc = t.replace(tzinfo=dt.timezone.utc) if t.tzinfo is None else t.astimezone(dt.timezone.utc)
            result.append(
                NormalizedCandle(
                    source=self.source,
                    market=market,
                    timeframe="1d",  # best-effort default for current wrapper
                    open_time_utc=t_utc,
                    open=float(c.open),
                    high=float(c.high),
                    low=float(c.low),
                    close=float(c.close),
                    volume_base=None,
                    volume_quote=None,
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
        _ = normalize_timeframe(timeframe)  # validate
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end must be timezone-aware (UTC)")

        if market.quote_asset.upper() not in {"USD", "USDT"}:
            logger.warning("coingecko provider uses USD quotes", market=market)

        # Best-effort with current project wrapper: returns 1d OHLC for last day.
        candles = await self._fetch_sync(market.base_asset)
        return [c for c in candles if start <= c.open_time_utc <= end]

