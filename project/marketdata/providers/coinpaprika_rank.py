from __future__ import annotations

import structlog
import httpx

from project.marketdata.providers.market_rank import RankedCoin
from project.services.stablecoins import STABLE_SYMBOL_DENYLIST


logger = structlog.get_logger(__name__)

COINPAPRIKA_TICKERS_URL = "https://api.coinpaprika.com/v1/tickers"


class CoinPaprikaMarketRankProvider:
    source = "coinpaprika"

    async def fetch_top_by_market_cap(self, *, limit: int) -> list[RankedCoin]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(COINPAPRIKA_TICKERS_URL, params={"quotes": "USD"})
            r.raise_for_status()
            payload = r.json()

        coins: list[RankedCoin] = []
        seen: set[str] = set()

        # coinpaprika returns a large list; rank is already numeric and roughly market-cap ordered.
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

