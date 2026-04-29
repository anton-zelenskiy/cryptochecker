from __future__ import annotations

import structlog
from sqlalchemy import delete, insert

from project.api.coingecko import CoingeckoMarketAPI
from project.core.db_session import sessionmanager
from project.models.catalog import CatalogCoin


logger = structlog.get_logger(__name__)

STABLE_SYMBOL_DENYLIST = {
    "usdt",
    "usdc",
    "dai",
    "tusd",
    "fdusd",
    "usdp",
    "pyusd",
    "usde",
    "frax",
}


async def refresh_catalog_top300_non_stablecoins() -> None:
    """
    Best-effort catalog refresh.

    Current CoinGecko wrapper doesn't expose `/coins/markets` with ranks in this repo,
    so we use `get_currency_code_id_map()` as a minimal starting point and mark stablecoins via denylist.

    Implementation can be upgraded to use direct httpx calls to `/coins/markets`.
    """
    api = CoingeckoMarketAPI()
    code_to_id = api.get_currency_code_id_map()

    # Minimal: store first 300 by iteration order (not ideal), but enables symbol mapping in MVP.
    rows = []
    for i, (symbol, coin_id) in enumerate(code_to_id.items()):
        if i >= 300:
            break
        is_stable = symbol.lower() in STABLE_SYMBOL_DENYLIST
        if is_stable:
            continue
        rows.append(
            {
                "coingecko_id": str(coin_id),
                "symbol": symbol.lower(),
                "name": str(coin_id),
                "market_cap_rank": i + 1,
                "is_stablecoin": False,
            }
        )

    async with sessionmanager.session() as session:
        await session.execute(delete(CatalogCoin))
        if rows:
            await session.execute(insert(CatalogCoin).values(rows))
        await session.commit()

    logger.info("catalog refreshed", rows=len(rows))

