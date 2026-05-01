from __future__ import annotations

import datetime as dt
from typing import Protocol

from project.marketdata.dto import NormalizedCandle, NormalizedMarket


class CandleSource(Protocol):
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
        """Fetch OHLCV candles in [start, end] (UTC). Implementations may ignore `limit`."""
