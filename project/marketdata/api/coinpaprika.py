from __future__ import annotations

import httpx

from project.core.caches import cached_method
from project.core.http_client import RateLimitPolicy, get_json_with_retries
from project.core.rate_limit_provider import get_rate_limiter
from project.marketdata.dto import RankedCoin
from project.services.stablecoins import STABLE_SYMBOL_DENYLIST


COINPAPRIKA_TICKERS_URL = "https://api.coinpaprika.com/v1/tickers"


class CoinPaprikaApi:
    source = "coinpaprika"

    @cached_method(key_prefix="market_rank:coinpaprika", ttl=60 * 60 * 24)
    async def fetch_top_by_market_cap(self, *, limit: int) -> list[RankedCoin]:
        rate_limiter = await get_rate_limiter()
        rate = RateLimitPolicy(key="ratelimit:coinpaprika:tickers", limit=4, window_s=60)

        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = await get_json_with_retries(
                client,
                url=COINPAPRIKA_TICKERS_URL,
                params={"quotes": "USD"},
                rate_limiter=rate_limiter,
                rate_limit=rate,
                max_attempts=3,
            )
            if not isinstance(payload, list):
                return []

        coins: list[RankedCoin] = []
        seen: set[str] = set()

        for item in payload:
            if len(coins) >= limit:
                break
            cid = str(item.get("id", ""))
            if not cid or cid in seen:
                continue
            symbol = str(item.get("symbol", "")).lower()
            if symbol in STABLE_SYMBOL_DENYLIST:
                continue
            name = str(item.get("name", ""))[:128] or cid
            rank = item.get("rank")
            coins.append(
                RankedCoin(
                    source=self.source,
                    coin_id=cid,
                    symbol=symbol,
                    name=name,
                    market_cap_rank=int(rank) if rank is not None else None,
                    is_stablecoin=False,
                )
            )
            seen.add(cid)

        return coins
