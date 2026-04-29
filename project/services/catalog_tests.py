from __future__ import annotations

import pytest

from project.services import catalog as catalog_module
from project.services.stablecoins import STABLE_SYMBOL_DENYLIST
from project.marketdata.providers.market_rank import ProviderRateLimited, RankedCoin


def test_stable_symbols_filtered_from_row_building() -> None:
    assert "usdt" in STABLE_SYMBOL_DENYLIST


@pytest.mark.asyncio
async def test_fetch_top300_falls_back_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_primary(self, *, limit: int) -> list[RankedCoin]:
        raise ProviderRateLimited("429")

    async def fake_fallback(self, *, limit: int) -> list[RankedCoin]:
        return [
            RankedCoin(source="coinpaprika", coin_id="btc-bitcoin", symbol="btc", name="Bitcoin", market_cap_rank=1),
            RankedCoin(source="coinpaprika", coin_id="eth-ethereum", symbol="eth", name="Ethereum", market_cap_rank=2),
        ]

    monkeypatch.setattr(
        "project.marketdata.providers.coingecko_rank.CoinGeckoMarketRankProvider.fetch_top_by_market_cap",
        fake_primary,
    )
    monkeypatch.setattr(
        "project.marketdata.providers.coinpaprika_rank.CoinPaprikaMarketRankProvider.fetch_top_by_market_cap",
        fake_fallback,
    )

    rows = await catalog_module.fetch_top300_non_stablecoin_rows()
    assert rows[0]["source"] == "coinpaprika"
    assert {r["coingecko_id"] for r in rows} == {"btc-bitcoin", "eth-ethereum"}
