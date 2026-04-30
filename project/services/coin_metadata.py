from __future__ import annotations

import datetime as dt

import httpx
import structlog

from project.core.config import settings
from project.core.http_client import RateLimitPolicy, get_json_with_retries
from project.core.rate_limit_provider import get_rate_limiter
from project.repositories.catalog import CatalogRepository
from project.repositories.coin_metadata import CoinMetadataRepository


logger = structlog.get_logger(__name__)

COINGECKO_COIN_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}"


async def _fetch_coingecko_platforms(client: httpx.AsyncClient, *, coin_id: str) -> dict | None:
    rate_limiter = await get_rate_limiter()
    rate = RateLimitPolicy(key="ratelimit:coingecko:coin", limit=6, window_s=60)
    headers = {"x-cg-demo-api-key": settings.COINGECKO_API_KEY} if settings.COINGECKO_API_KEY else None
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
            logger.warning("coingecko rate limited on coin metadata", coin_id=coin_id)
            return None
        raise

    platforms = payload.get("platforms")
    if isinstance(platforms, dict):
        return platforms
    return None


async def refresh_coin_metadata_platforms_from_catalog(*, limit: int = 300) -> int:
    """
    Best-effort nightly job: store CoinGecko `platforms` (chain->contract) for catalog coins.

    Stops early on 429 to avoid burning quota.
    """
    catalog_repo = CatalogRepository()
    coins = await catalog_repo.list_by_market_cap_rank(source="coingecko", limit=limit)

    if not coins:
        logger.info("no coins to refresh", limit=limit)
        return 0

    fetched_at = dt.datetime.now(dt.timezone.utc)
    updated = 0
    repo = CoinMetadataRepository()

    async with httpx.AsyncClient(timeout=45.0) as client:
        for c in coins:
            platforms = await _fetch_coingecko_platforms(client, coin_id=c.coingecko_id)
            logger.info("fetched platforms", coin_id=c.coingecko_id, platforms=platforms)
            if platforms is None:
                break
            await repo.upsert_platforms(coin_id=c.coingecko_id, platforms=platforms, fetched_at=fetched_at)
            updated += 1

    logger.info("coin metadata refreshed", updated=updated)
    return updated

