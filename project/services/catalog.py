from __future__ import annotations

import structlog
from project.models.catalog import CatalogCoin
from project.marketdata.providers.coingecko_rank import CoinGeckoMarketRankProvider
from project.marketdata.providers.coinpaprika_rank import CoinPaprikaMarketRankProvider
from project.marketdata.providers.market_rank import ProviderRateLimited, RankedCoin
from project.repositories.catalog import CatalogRepository


logger = structlog.get_logger(__name__)

def _ranked_coins_to_rows(coins: list[RankedCoin], *, limit: int) -> list[dict]:
    rows: list[dict] = []
    for c in coins[:limit]:
        rows.append(
            {
                "source": c.source,
                "coingecko_id": c.coin_id,
                "symbol": c.symbol,
                "name": c.name,
                "market_cap_rank": c.market_cap_rank,
                "is_stablecoin": bool(c.is_stablecoin),
            }
        )
    return rows


async def fetch_top300_non_stablecoin_rows() -> list[dict]:
    """
    Fetch top 300 non-stablecoins by market cap rank.

    Primary: CoinGecko. Fallback: CoinPaprika when CoinGecko hits 429/rate limits.
    """
    cg = CoinGeckoMarketRankProvider()
    try:
        coins = await cg.fetch_top_by_market_cap(limit=300)
        return _ranked_coins_to_rows(coins, limit=300)
    except ProviderRateLimited:
        logger.warning("catalog primary rate limited, falling back", primary=cg.source)
    except Exception as e:
        logger.warning("catalog primary failed, falling back", primary=cg.source, error=str(e))

    fb = CoinPaprikaMarketRankProvider()
    coins = await fb.fetch_top_by_market_cap(limit=300)
    return _ranked_coins_to_rows(coins, limit=300)


async def refresh_catalog_top300_non_stablecoins() -> None:
    """
    Replace catalog with top ~300 non-stable coins by market cap (CoinGecko public API).

    If the fetch returns nothing (network/429), existing rows are left unchanged.
    """
    try:
        rows = await fetch_top300_non_stablecoin_rows()
    except Exception as e:
        logger.warning("catalog fetch failed", error=str(e))
        return

    if not rows:
        logger.warning("catalog refresh skipped: empty result")
        return

    repo = CatalogRepository()
    await repo.replace_all(rows)

    logger.info("catalog refreshed", rows=len(rows))
