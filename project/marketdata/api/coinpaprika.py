from __future__ import annotations

import httpx
import structlog

from project.core.caches import cached_method
from project.core.http_client import RateLimitPolicy, get_json
from project.core.rate_limit_provider import get_rate_limiter
from project.marketdata.coinpaprika_stablecoin_tag import coin_ids_from_stablecoin_tag_payload
from project.marketdata.dto import RankedCoin


logger = structlog.get_logger(__name__)

COINPAPRIKA_TICKERS_URL = "https://api.coinpaprika.com/v1/tickers"
COINPAPRIKA_STABLECOIN_TAG_URL = "https://api.coinpaprika.com/v1/tags/stablecoin"


class CoinPaprikaApi:
    source = "coinpaprika"

    @cached_method(key_prefix="coinpaprika:tag_stablecoin_coins", ttl=60 * 60 * 6)
    async def _stablecoin_coin_ids(self) -> frozenset[str]:
        rate_limiter = await get_rate_limiter()
        rate = RateLimitPolicy(key="ratelimit:coinpaprika:tags", limit=4, window_s=60)
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                payload = await get_json(
                    client,
                    url=COINPAPRIKA_STABLECOIN_TAG_URL,
                    params={"additional_fields": "coins"},
                    rate_limiter=rate_limiter,
                    rate_limit=rate,
                    max_attempts=2,
                )
            except httpx.HTTPStatusError as e:
                code = e.response.status_code if e.response is not None else None
                logger.warning("coinpaprika stablecoin tag request failed", status_code=code)
                return frozenset()

        return coin_ids_from_stablecoin_tag_payload(payload)

    @cached_method(key_prefix="market_rank:coinpaprika", ttl=60 * 60 * 24)
    async def fetch_top_by_market_cap(self, *, limit: int) -> list[RankedCoin]:
        rate_limiter = await get_rate_limiter()
        rate = RateLimitPolicy(key="ratelimit:coinpaprika:tickers", limit=4, window_s=60)

        stable_ids = await self._stablecoin_coin_ids()

        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = await get_json(
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
            if cid in stable_ids:
                continue
            symbol = str(item.get("symbol", "")).lower()
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
