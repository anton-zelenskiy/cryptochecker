from __future__ import annotations

import datetime as dt
from collections.abc import Protocol

from project.marketdata.dto import NormalizedCandle, NormalizedMarket


class CandleProvider(Protocol):
    source: str

    async def fetch_ohlcv(
        self,
        market: NormalizedMarket,
        timeframe: str,
        start: dt.datetime,
        end: dt.datetime,
        *,
        limit: int | None = None,
    ) -> list[NormalizedCandle]:
        """
        Fetch OHLCV candles in [start, end] (UTC).

        Providers may ignore `limit` if their API doesn't support it.
        """

