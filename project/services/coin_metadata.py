from __future__ import annotations

import datetime as dt

import structlog

from project.marketdata.api.coingecko import CoinGeckoApi
from project.repositories.catalog import CatalogRepository
from project.repositories.coin_metadata import CoinMetadataRepository


logger = structlog.get_logger(__name__)


def _extract_platforms(payload: dict) -> dict | None:
    platforms = payload.get("platforms")
    return platforms if isinstance(platforms, dict) else None


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
    api = CoinGeckoApi()

    for c in coins:
        payload = await api.get_coin_details(coin_id=c.coingecko_id)
        platforms = _extract_platforms(payload) if payload is not None else None
        logger.info("fetched platforms", coin_id=c.coingecko_id, platforms=platforms)
        if platforms is None:
            break
        await repo.upsert_platforms(coin_id=c.coingecko_id, platforms=platforms, fetched_at=fetched_at)
        updated += 1

    logger.info("coin metadata refreshed", updated=updated)
    return updated

