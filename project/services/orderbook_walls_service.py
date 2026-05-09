from __future__ import annotations

import asyncio
import statistics

import structlog

from project.core.config import settings
from project.marketdata.api.bybit import collect_orderbook_walls_for_markets as collect_bybit_orderbook_walls
from project.marketdata.api.kucoin import collect_orderbook_walls_for_markets as collect_kucoin_orderbook_walls
from project.marketdata.dto import NormalizedMarket
from project.repositories.candles import CandleRepository
from project.repositories.orderbook_walls import OrderBookWallRepository
from project.repositories.users import UserTrackedAssetRepository
from project.screener.volume_regime import CandleOHLCV, compute_volume_regime


logger = structlog.get_logger(__name__)


def _range_pct_from_candle(c: CandleOHLCV) -> float | None:
    if not c.close:
        return None
    try:
        return float(c.high - c.low) / float(c.close)
    except Exception:
        return None


def _dynamic_wall_thresholds_for_market(
    *,
    vol_feat: object,
    median_range_pct: float | None,
) -> tuple[float, float]:
    avg_daily = getattr(vol_feat, "avg_daily_volume_quote", None)
    if avg_daily is None or avg_daily <= 0:
        avg_daily = 50_000_000.0

    base_min_notional = max(5_000.0, min(150_000.0, float(avg_daily) * 0.0003))

    vol_factor = 1.0
    if median_range_pct is not None:
        if median_range_pct >= 0.05:
            vol_factor = 1.5
        elif median_range_pct <= 0.02:
            vol_factor = 0.85

    spike = bool(getattr(vol_feat, "is_sharp_spike", False))
    spike_factor = 1.2 if spike else 1.0

    min_notional_quote = float(base_min_notional * vol_factor * spike_factor)

    qty_mult = 6.0
    if median_range_pct is not None and median_range_pct >= 0.05:
        qty_mult += 2.0
    if median_range_pct is not None and median_range_pct <= 0.02:
        qty_mult -= 1.0
    if spike:
        qty_mult -= 0.75
    qty_vs_median_multiplier = float(max(4.0, min(10.0, qty_mult)))

    return min_notional_quote, qty_vs_median_multiplier


class OrderBookWallsService:
    async def ingest_tracked_orderbook_walls(self, *, duration_s: float = 20.0, max_markets: int = 10) -> int:
        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()

        if not markets:
            return 0

        normalized = [NormalizedMarket(base_asset=b, quote_asset=q) for b, q in sorted(markets)]

        candle_repo = CandleRepository()
        bybit_min_notional_by_sym: dict[str, float] = {}
        bybit_qty_mult_by_sym: dict[str, float] = {}
        kucoin_min_notional_by_sym: dict[str, float] = {}
        kucoin_qty_mult_by_sym: dict[str, float] = {}

        for m in normalized[:max_markets]:
            candles = await candle_repo.list_latest_n(
                source="bybit",
                base_asset=m.base_asset.upper(),
                quote_asset=m.quote_asset.upper(),
                timeframe="1h",
                limit=900,
            )
            if not candles:
                candles = await candle_repo.list_latest_n(
                    source="kucoin",
                    base_asset=m.base_asset.upper(),
                    quote_asset=m.quote_asset.upper(),
                    timeframe="1h",
                    limit=900,
                )
            if not candles:
                continue

            ohlcv = [
                CandleOHLCV(
                    open_time_utc=c.open_time_utc,
                    open=float(c.open),
                    high=float(c.high),
                    low=float(c.low),
                    close=float(c.close),
                    volume_quote=float(c.volume_quote) if c.volume_quote is not None else None,
                    volume_base=float(c.volume_base) if c.volume_base is not None else None,
                )
                for c in candles
            ]
            vol_feat = compute_volume_regime(ohlcv, lookback_days=14)
            last48 = ohlcv[-48:] if len(ohlcv) >= 48 else ohlcv
            ranges = [v for v in (_range_pct_from_candle(c) for c in last48) if v is not None]
            median_range_pct = float(statistics.median(ranges)) if ranges else None

            min_notional, qty_mult = _dynamic_wall_thresholds_for_market(
                vol_feat=vol_feat,
                median_range_pct=median_range_pct,
            )

            bybit_sym = f"{m.base_asset.upper()}{m.quote_asset.upper()}"
            kucoin_sym = f"{m.base_asset.upper()}-{m.quote_asset.upper()}"
            bybit_min_notional_by_sym[bybit_sym] = min_notional
            bybit_qty_mult_by_sym[bybit_sym] = qty_mult
            kucoin_min_notional_by_sym[kucoin_sym] = min_notional
            kucoin_qty_mult_by_sym[kucoin_sym] = qty_mult

        if bybit_min_notional_by_sym:
            logger.info("dynamic wall thresholds computed", markets=len(bybit_min_notional_by_sym))

        bybit_headers = {"X-BAPI-API-KEY": settings.BYBIT_API_KEY} if settings.BYBIT_API_KEY else None
        kucoin_headers = None
        if settings.KUCOIN_API_KEY:
            kucoin_headers = {"KC-API-KEY": settings.KUCOIN_API_KEY}

        bybit_rows, kucoin_rows = await asyncio.gather(
            collect_bybit_orderbook_walls(
                normalized,
                duration_s=duration_s,
                max_markets=max_markets,
                extra_headers=bybit_headers,
                min_notional_quote_by_sym=bybit_min_notional_by_sym or None,
                qty_vs_median_multiplier_by_sym=bybit_qty_mult_by_sym or None,
            ),
            collect_kucoin_orderbook_walls(
                normalized,
                duration_s=duration_s,
                max_markets=max_markets,
                extra_headers=kucoin_headers,
                min_notional_quote_by_sym=kucoin_min_notional_by_sym or None,
                qty_vs_median_multiplier_by_sym=kucoin_qty_mult_by_sym or None,
            ),
        )
        rows = [*bybit_rows, *kucoin_rows]
        if not rows:
            return 0

        await OrderBookWallRepository().bulk_insert_ignore_conflicts(
            rows,
            conflict_constraint="uq_orderbook_wall_identity",
        )

        logger.info("orderbook walls attempted", candidates=len(rows))
        return len(rows)
