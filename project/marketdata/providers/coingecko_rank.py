from __future__ import annotations

import structlog
import httpx

from project.marketdata.providers.market_rank import ProviderRateLimited, RankedCoin
from project.services.stablecoins import STABLE_SYMBOL_DENYLIST


logger = structlog.get_logger(__name__)

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"


class CoinGeckoMarketRankProvider:
    source = "coingecko"

    async def fetch_top_by_market_cap(self, *, limit: int) -> list[RankedCoin]:
        coins: list[RankedCoin] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=45.0) as client:
            for page in (1, 2, 3, 4, 5):
                if len(coins) >= limit:
                    break
                r = await client.get(
                    COINGECKO_MARKETS_URL,
                    params={
                        "vs_currency": "usd",
                        "order": "market_cap_desc",
                        "per_page": 100,
                        "page": page,
                        "sparkline": "false",
                    },
                )
                if r.status_code == 429:
                    logger.warning("coingecko rate limited on ranks", page=page)
                    raise ProviderRateLimited("coingecko 429")
                r.raise_for_status()
                batch = r.json()
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

