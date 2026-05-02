from __future__ import annotations

import datetime as dt

import structlog

from project.marketdata.api.coingecko import CoinGeckoApi
from project.models.screener import FundamentalsSnapshot
from project.repositories.catalog import CatalogRepository
from project.repositories.fundamentals_snapshots import FundamentalsSnapshotRepository
from project.repositories.users import UserTrackedAssetRepository


logger = structlog.get_logger(__name__)


def _parse_usd(obj: object) -> float | None:
    if isinstance(obj, dict):
        v = obj.get("usd")
        return float(v) if v is not None else None
    if isinstance(obj, (int, float)):
        return float(obj)
    return None


def _compute_flags(
    *,
    mcap: float | None,
    fdv: float | None,
    tvl: float | None,
) -> tuple[float | None, float | None, bool, bool, bool]:
    tvl_unavailable = tvl is None or tvl <= 0
    mcap_to_tvl = (mcap / tvl) if mcap and tvl and tvl > 0 else None
    fdv_to_tvl = (fdv / tvl) if fdv and tvl and tvl > 0 else None
    overpriced = bool(
        not tvl_unavailable
        and (
            (mcap_to_tvl is not None and mcap_to_tvl > 40.0)
            or (fdv_to_tvl is not None and fdv_to_tvl > 60.0)
        )
    )
    undervalued = bool(
        not tvl_unavailable
        and mcap_to_tvl is not None
        and mcap_to_tvl < 2.5
        and (fdv_to_tvl is None or fdv_to_tvl < 4.0)
    )
    return mcap_to_tvl, fdv_to_tvl, overpriced, undervalued, tvl_unavailable


def _snapshot_row_to_dict(snap: FundamentalsSnapshot) -> dict:
    return {
        "coingecko_id": snap.coingecko_id,
        "market_cap_usd": snap.market_cap_usd,
        "fdv_usd": snap.fdv_usd,
        "total_volume_24h_usd": snap.total_volume_24h_usd,
        "tvl_usd": snap.tvl_usd,
        "mcap_to_tvl": snap.mcap_to_tvl,
        "fdv_to_tvl": snap.fdv_to_tvl,
        "flag_overpriced": snap.flag_overpriced,
        "flag_undervalued_tvl": snap.flag_undervalued_tvl,
        "tvl_unavailable": snap.tvl_unavailable,
    }


async def get_latest_fundamentals_dict_from_db(*, coingecko_id: str) -> dict | None:
    repo = FundamentalsSnapshotRepository()
    existing = await repo.get_latest_for_coingecko_id(coingecko_id=coingecko_id)
    if not existing:
        return None
    return _snapshot_row_to_dict(existing)


async def fetch_and_store_fundamentals_if_stale(
    *,
    coingecko_id: str,
    base_symbol: str,
    max_age_hours: int = 6,
    force: bool = False,
) -> dict | None:
    repo = FundamentalsSnapshotRepository()
    existing = await repo.get_latest_for_coingecko_id(coingecko_id=coingecko_id)
    now = dt.datetime.now(dt.timezone.utc)
    if (
        not force
        and existing
        and (now - existing.fetched_at).total_seconds() < max_age_hours * 3600
    ):
        return _snapshot_row_to_dict(existing)

    payload = await CoinGeckoApi().get_coin_with_market_data(coin_id=coingecko_id)
    if not payload:
        logger.warning("no payload from coingecko", coingecko_id=coingecko_id)
        return None

    md = payload.get("market_data")
    if not isinstance(md, dict):
        logger.warning("no market data from coingecko", coingecko_id=coingecko_id)
        return None

    mcap = _parse_usd(md.get("market_cap"))
    fdv = _parse_usd(md.get("fully_diluted_valuation"))
    vol = _parse_usd(md.get("total_volume"))
    tvl = _parse_usd(md.get("total_value_locked"))

    mcap_to_tvl, fdv_to_tvl, overpriced, undervalued, tvl_unavail = _compute_flags(
        mcap=mcap, fdv=fdv, tvl=tvl
    )

    row = {
        "coingecko_id": coingecko_id,
        "base_symbol": base_symbol.strip().upper(),
        "fetched_at": now,
        "market_cap_usd": mcap,
        "fdv_usd": fdv,
        "total_volume_24h_usd": vol,
        "tvl_usd": tvl,
        "mcap_to_tvl": mcap_to_tvl,
        "fdv_to_tvl": fdv_to_tvl,
        "flag_overpriced": overpriced,
        "flag_undervalued_tvl": undervalued,
        "tvl_unavailable": tvl_unavail,
        "raw_extras": None,
    }
    await repo.insert(row)
    logger.info("fundamentals stored", coingecko_id=coingecko_id, overpriced=overpriced)
    return {
        "coingecko_id": coingecko_id,
        "market_cap_usd": mcap,
        "fdv_usd": fdv,
        "total_volume_24h_usd": vol,
        "tvl_usd": tvl,
        "mcap_to_tvl": mcap_to_tvl,
        "fdv_to_tvl": fdv_to_tvl,
        "flag_overpriced": overpriced,
        "flag_undervalued_tvl": undervalued,
        "tvl_unavailable": tvl_unavail,
    }


async def refresh_tracked_fundamentals_snapshots() -> int:
    markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()
    logger.info("refreshing fundamentals snapshots", markets=markets)
    catalog = CatalogRepository()
    refreshed = 0
    seen_coingecko: set[str] = set()
    for base_asset, _quote in sorted(markets):
        cat = await catalog.get_first_by_symbol(source="coingecko", symbol=base_asset)
        logger.info("catalog", cat=cat)
        if not cat or cat.coingecko_id in seen_coingecko:
            logger.info("skipping", cat=cat)
            continue
        seen_coingecko.add(cat.coingecko_id)
        row = await fetch_and_store_fundamentals_if_stale(
            coingecko_id=cat.coingecko_id,
            base_symbol=base_asset,
            force=True,
        )
        if row:
            refreshed += 1
    return refreshed
