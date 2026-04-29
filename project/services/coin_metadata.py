from __future__ import annotations

import datetime as dt

import httpx
import structlog
from sqlalchemy import insert, select

from project.core.db_session import sessionmanager
from project.models.catalog import CatalogCoin
from project.models.coin_metadata import CoinMetadata


logger = structlog.get_logger(__name__)

COINGECKO_COIN_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}"


async def _fetch_coingecko_platforms(client: httpx.AsyncClient, *, coin_id: str) -> dict | None:
    r = await client.get(
        COINGECKO_COIN_URL.format(coin_id=coin_id),
        params={
            "localization": "false",
            "tickers": "false",
            "market_data": "false",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false",
        },
    )
    if r.status_code == 429:
        logger.warning("coingecko rate limited on coin metadata", coin_id=coin_id)
        return None
    r.raise_for_status()
    payload = r.json()
    platforms = payload.get("platforms")
    if isinstance(platforms, dict):
        return platforms
    return None


async def refresh_coin_metadata_platforms_from_catalog(*, limit: int = 300) -> int:
    """
    Best-effort nightly job: store CoinGecko `platforms` (chain->contract) for catalog coins.

    Stops early on 429 to avoid burning quota.
    """
    async with sessionmanager.session() as session:
        res = await session.execute(
            select(CatalogCoin)
            .where(CatalogCoin.source == "coingecko")
            .order_by(CatalogCoin.market_cap_rank.asc())
            .limit(limit)
        )
        coins = list(res.scalars().all())

    if not coins:
        return 0

    fetched_at = dt.datetime.now(dt.timezone.utc)
    updated = 0

    async with httpx.AsyncClient(timeout=45.0) as client:
        async with sessionmanager.session() as session:
            for c in coins:
                platforms = await _fetch_coingecko_platforms(client, coin_id=c.coingecko_id)
                if platforms is None:
                    break

                row = {
                    "source": "coingecko",
                    "coin_id": c.coingecko_id,
                    "platforms": platforms,
                    "fetched_at": fetched_at,
                }

                stmt = insert(CoinMetadata).values([row])
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_coin_metadata_identity",
                    set_={
                        "platforms": stmt.excluded.platforms,
                        "fetched_at": stmt.excluded.fetched_at,
                        "updated_at": dt.datetime.now(dt.timezone.utc),
                    },
                )
                await session.execute(stmt)
                updated += 1

            await session.commit()

    logger.info("coin metadata refreshed", updated=updated)
    return updated

