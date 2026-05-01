from __future__ import annotations

import httpx
import structlog

from project.core.caches import cached_method
from project.core.config import settings
from project.core.http_client import RateLimitPolicy, get_json_with_retries
from project.core.rate_limit_provider import get_rate_limiter
from project.marketdata.dto import RankedCoin
from project.marketdata.exceptions import ProviderRateLimited
from project.services.stablecoins import STABLE_SYMBOL_DENYLIST


logger = structlog.get_logger(__name__)

COINGECKO_COIN_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"


class CoinGeckoApi:
    source = "coingecko"

    @cached_method(key_prefix="coingecko:coin_details", ttl=60 * 60 * 24)
    async def get_coin_details(self, *, coin_id: str) -> dict | None:
        rate_limiter = await get_rate_limiter()
        rate = RateLimitPolicy(key="ratelimit:coingecko:coin", limit=6, window_s=60)
        headers = {"x-cg-demo-api-key": settings.COINGECKO_API_KEY} if settings.COINGECKO_API_KEY else None

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                payload = await get_json_with_retries(
                    client,
                    url=COINGECKO_COIN_URL.format(coin_id=coin_id),
                    params={
                        "localization": "false",
                        "tickers": "false",
                        "market_data": "false",
                        "community_data": "false",
                        "developer_data": "false",
                        "sparkline": "false",
                    },
                    headers=headers,
                    rate_limiter=rate_limiter,
                    rate_limit=rate,
                    max_attempts=3,
                )
            except httpx.HTTPStatusError as e:
                if e.response is not None and e.response.status_code == 429:
                    logger.warning("coingecko rate limited on coin details", coin_id=coin_id)
                    return None
                raise

        return payload if isinstance(payload, dict) else None

    async def list_markets_by_market_cap(self, *, page: int) -> list[dict] | None:
        rate_limiter = await get_rate_limiter()
        rate = RateLimitPolicy(key="ratelimit:coingecko:coins_markets", limit=8, window_s=60)
        headers = {"x-cg-demo-api-key": settings.COINGECKO_API_KEY} if settings.COINGECKO_API_KEY else None

        async with httpx.AsyncClient(timeout=45.0) as client:
            payload = await get_json_with_retries(
                client,
                url=COINGECKO_MARKETS_URL,
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 100,
                    "page": page,
                    "sparkline": "false",
                },
                headers=headers,
                rate_limiter=rate_limiter,
                rate_limit=rate,
                max_attempts=3,
            )

        return payload if isinstance(payload, list) else None

    @cached_method(key_prefix="market_rank:coingecko", ttl=60 * 60 * 24)
    async def fetch_top_by_market_cap(self, *, limit: int) -> list[RankedCoin]:
        coins: list[RankedCoin] = []
        seen: set[str] = set()

        for page in (1, 2, 3, 4, 5):
            if len(coins) >= limit:
                break
            try:
                batch = await self.list_markets_by_market_cap(page=page)
            except httpx.HTTPStatusError as e:
                if e.response is not None and e.response.status_code == 429:
                    logger.warning("coingecko rate limited on ranks", page=page)
                    raise ProviderRateLimited("coingecko 429") from e
                raise
            if not batch:
                break

            for coin in batch:
                if len(coins) >= limit:
                    break
                cid = str(coin.get("id", ""))
                if not cid or cid in seen:
                    continue
                symbol = str(coin.get("symbol", "")).lower()
                if symbol in STABLE_SYMBOL_DENYLIST:
                    continue
                name = str(coin.get("name", ""))[:128] or cid
                rank = coin.get("market_cap_rank")
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
