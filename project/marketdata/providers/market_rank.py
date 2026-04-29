from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RankedCoin:
    source: str
    coin_id: str
    symbol: str
    name: str
    market_cap_rank: int | None
    is_stablecoin: bool = False


class MarketRankProvider(Protocol):
    source: str

    async def fetch_top_by_market_cap(self, *, limit: int) -> list[RankedCoin]:
        raise NotImplementedError


class ProviderRateLimited(Exception):
    pass

