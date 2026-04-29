from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NormalizedMarket:
    base_asset: str
    quote_asset: str = "USDT"

    @property
    def symbol(self) -> str:
        return f"{self.base_asset.upper()}{self.quote_asset.upper()}"

    @property
    def pair(self) -> str:
        return f"{self.base_asset.upper()}-{self.quote_asset.upper()}"


@dataclass(frozen=True, slots=True)
class NormalizedCandle:
    source: str
    market: NormalizedMarket
    timeframe: str  # e.g. "1m", "5m", "1h"
    open_time_utc: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume_base: float | None = None
    volume_quote: float | None = None

    def __post_init__(self) -> None:
        if self.open_time_utc.tzinfo is None:
            raise ValueError("open_time_utc must be timezone-aware (UTC)")

