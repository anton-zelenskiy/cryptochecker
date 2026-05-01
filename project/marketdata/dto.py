from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, computed_field, field_validator


class NormalizedMarket(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_asset: str
    quote_asset: str = "USDT"

    @computed_field
    @property
    def symbol(self) -> str:
        return f"{self.base_asset.upper()}{self.quote_asset.upper()}"

    @computed_field
    @property
    def pair(self) -> str:
        return f"{self.base_asset.upper()}-{self.quote_asset.upper()}"


class NormalizedCandle(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    market: NormalizedMarket
    timeframe: str
    open_time_utc: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume_base: float | None = None
    volume_quote: float | None = None

    @field_validator("open_time_utc")
    @classmethod
    def open_time_must_be_aware_utc(cls, v: dt.datetime) -> dt.datetime:
        if v.tzinfo is None:
            raise ValueError("open_time_utc must be timezone-aware (UTC)")
        return v


class RankedCoin(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    coin_id: str
    symbol: str
    name: str
    market_cap_rank: int | None
    is_stablecoin: bool = False
