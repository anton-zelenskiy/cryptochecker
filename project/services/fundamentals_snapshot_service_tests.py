from __future__ import annotations

import datetime as dt

import pytest

from project.models.screener import FundamentalsSnapshot
from project.repositories.fundamentals_snapshots import FundamentalsSnapshotRepository
from project.services import fundamentals_snapshot_service as fss


@pytest.mark.asyncio
async def test_get_latest_fundamentals_dict_from_db_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_latest(self: FundamentalsSnapshotRepository, *, coingecko_id: str) -> None:
        return None

    monkeypatch.setattr(
        FundamentalsSnapshotRepository,
        "get_latest_for_coingecko_id",
        fake_get_latest,
    )
    assert await fss.get_latest_fundamentals_dict_from_db(coingecko_id="bitcoin") is None


@pytest.mark.asyncio
async def test_get_latest_fundamentals_dict_from_db_returns_row(monkeypatch: pytest.MonkeyPatch) -> None:
    snap = FundamentalsSnapshot(
        coingecko_id="bitcoin",
        base_symbol="BTC",
        fetched_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        market_cap_usd=1e12,
        fdv_usd=2e12,
        total_volume_24h_usd=50e9,
        tvl_usd=None,
        mcap_to_tvl=None,
        fdv_to_tvl=None,
        flag_overpriced=False,
        flag_undervalued_tvl=False,
        tvl_unavailable=True,
    )

    async def fake_get_latest(
        self: FundamentalsSnapshotRepository, *, coingecko_id: str
    ) -> FundamentalsSnapshot | None:
        return snap if coingecko_id == "bitcoin" else None

    monkeypatch.setattr(
        FundamentalsSnapshotRepository,
        "get_latest_for_coingecko_id",
        fake_get_latest,
    )
    d = await fss.get_latest_fundamentals_dict_from_db(coingecko_id="bitcoin")
    assert d is not None
    assert d["coingecko_id"] == "bitcoin"
    assert d["market_cap_usd"] == 1e12
    assert d["tvl_unavailable"] is True


@pytest.mark.asyncio
async def test_fetch_and_store_respects_fresh_cache_without_force(monkeypatch: pytest.MonkeyPatch) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    snap = FundamentalsSnapshot(
        coingecko_id="bitcoin",
        base_symbol="BTC",
        fetched_at=now,
        market_cap_usd=99.0,
        fdv_usd=None,
        total_volume_24h_usd=None,
        tvl_usd=None,
        mcap_to_tvl=None,
        fdv_to_tvl=None,
        flag_overpriced=False,
        flag_undervalued_tvl=False,
        tvl_unavailable=True,
    )

    async def fake_get_latest(
        self: FundamentalsSnapshotRepository, *, coingecko_id: str
    ) -> FundamentalsSnapshot | None:
        return snap

    called: list[str] = []

    async def fake_api(self, *, coin_id: str) -> dict:
        called.append(coin_id)
        return {}

    monkeypatch.setattr(
        FundamentalsSnapshotRepository,
        "get_latest_for_coingecko_id",
        fake_get_latest,
    )
    monkeypatch.setattr(
        "project.services.fundamentals_snapshot_service.CoinGeckoApi.get_coin_with_market_data",
        fake_api,
    )
    out = await fss.fetch_and_store_fundamentals_if_stale(
        coingecko_id="bitcoin",
        base_symbol="BTC",
        max_age_hours=6,
        force=False,
    )
    assert out is not None
    assert out["market_cap_usd"] == 99.0
    assert called == []


@pytest.mark.asyncio
async def test_fetch_and_store_force_bypasses_fresh_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    snap = FundamentalsSnapshot(
        coingecko_id="bitcoin",
        base_symbol="BTC",
        fetched_at=now,
        market_cap_usd=99.0,
        fdv_usd=None,
        total_volume_24h_usd=None,
        tvl_usd=None,
        mcap_to_tvl=None,
        fdv_to_tvl=None,
        flag_overpriced=False,
        flag_undervalued_tvl=False,
        tvl_unavailable=True,
    )

    async def fake_get_latest(
        self: FundamentalsSnapshotRepository, *, coingecko_id: str
    ) -> FundamentalsSnapshot | None:
        return snap

    async def fake_api(self, *, coin_id: str) -> dict:
        return {
            "market_data": {
                "market_cap": {"usd": 100.0},
                "fully_diluted_valuation": {"usd": 200.0},
                "total_volume": {"usd": 10.0},
                "total_value_locked": {"usd": 50.0},
            }
        }

    inserted: list[dict] = []

    async def fake_insert(self: FundamentalsSnapshotRepository, row: dict) -> FundamentalsSnapshot:
        inserted.append(row)
        return FundamentalsSnapshot(**row)

    monkeypatch.setattr(
        FundamentalsSnapshotRepository,
        "get_latest_for_coingecko_id",
        fake_get_latest,
    )
    monkeypatch.setattr(
        "project.services.fundamentals_snapshot_service.CoinGeckoApi.get_coin_with_market_data",
        fake_api,
    )
    monkeypatch.setattr(FundamentalsSnapshotRepository, "insert", fake_insert)

    out = await fss.fetch_and_store_fundamentals_if_stale(
        coingecko_id="bitcoin",
        base_symbol="BTC",
        force=True,
    )
    assert out is not None
    assert out["market_cap_usd"] == 100.0
    assert len(inserted) == 1
