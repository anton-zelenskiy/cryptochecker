from __future__ import annotations

import datetime as dt
import statistics

import structlog

from project.repositories.candles import CandleRepository
from project.repositories.trade_clusters import TradeClusterMarketThreshold, TradeClustersRepository
from project.repositories.users import UserTrackedAssetRepository
from project.screener.contracts import VolumeRegimeFeature
from project.screener.dynamic_market_thresholds import dynamic_wall_thresholds_for_market, range_pct_from_candle
from project.screener.volume_regime import CandleOHLCV, compute_volume_regime


logger = structlog.get_logger(__name__)


_TRADE_INGEST_SOURCES = frozenset({"bybit"})

VOLUME_REGIME_LOOKBACK_DAYS = 14
CLUSTER_CANDLE_TIMEFRAME = "1h"
CLUSTER_CANDLE_FETCH_LIMIT = 900
CLUSTER_MEDIAN_RANGE_LOOKBACK_HOURS = 48
CLUSTER_MIN_CLUSTER_NOTIONAL_FLOOR = 1.0
DEFAULT_CLUSTER_NOTIONAL_MULTIPLIER = 4.0
DEFAULT_TRADE_CLUSTER_LOOKBACK_S = 120
DEFAULT_TRADE_CLUSTER_WINDOW_S = 15
VOL_NOTE_NO_CANDLES_TRADE_CLUSTERS = "no_candles_trade_clusters"


async def compute_cluster_thresholds_for_tracked_markets(
    *,
    cluster_notional_multiplier: float,
) -> list[TradeClusterMarketThreshold]:
    markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()
    if not markets:
        return []

    candle_repo = CandleRepository()
    rows: list[TradeClusterMarketThreshold] = []

    def _baseline_min_trade(vol_note: str) -> float:
        min_trade, _ = dynamic_wall_thresholds_for_market(
            vol_feat=VolumeRegimeFeature(lookback_days=VOLUME_REGIME_LOOKBACK_DAYS, note=vol_note),
            median_range_pct=None,
        )
        return min_trade

    for base_asset, quote_asset in sorted(markets):
        candles = await candle_repo.list_latest_n(
            source="bybit",
            base_asset=base_asset.upper(),
            quote_asset=quote_asset.upper(),
            timeframe=CLUSTER_CANDLE_TIMEFRAME,
            limit=CLUSTER_CANDLE_FETCH_LIMIT,
        )
        if not candles:
            candles = await candle_repo.list_latest_n(
                source="kucoin",
                base_asset=base_asset.upper(),
                quote_asset=quote_asset.upper(),
                timeframe=CLUSTER_CANDLE_TIMEFRAME,
                limit=CLUSTER_CANDLE_FETCH_LIMIT,
            )

        min_trade_quote: float
        if candles:
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
            vol_feat = compute_volume_regime(ohlcv, lookback_days=VOLUME_REGIME_LOOKBACK_DAYS)
            tail = (
                ohlcv[-CLUSTER_MEDIAN_RANGE_LOOKBACK_HOURS:]
                if len(ohlcv) >= CLUSTER_MEDIAN_RANGE_LOOKBACK_HOURS
                else ohlcv
            )
            ranges = [v for v in (range_pct_from_candle(c) for c in tail) if v is not None]
            median_range_pct = float(statistics.median(ranges)) if ranges else None
            min_trade_quote, _ = dynamic_wall_thresholds_for_market(
                vol_feat=vol_feat,
                median_range_pct=median_range_pct,
            )
        else:
            min_trade_quote = _baseline_min_trade(vol_note=VOL_NOTE_NO_CANDLES_TRADE_CLUSTERS)

        min_cluster = max(
            CLUSTER_MIN_CLUSTER_NOTIONAL_FLOOR,
            float(min_trade_quote) * float(cluster_notional_multiplier),
        )

        for source in sorted(_TRADE_INGEST_SOURCES):
            rows.append(
                (
                    source,
                    base_asset.upper(),
                    quote_asset.upper(),
                    float(min_trade_quote),
                    float(min_cluster),
                )
            )

    return rows


class TradeClustersService:
    async def cluster_recent_large_buys(
        self,
        *,
        lookback_s: int = DEFAULT_TRADE_CLUSTER_LOOKBACK_S,
        window_s: int = DEFAULT_TRADE_CLUSTER_WINDOW_S,
        cluster_notional_multiplier: float = DEFAULT_CLUSTER_NOTIONAL_MULTIPLIER,
    ) -> int:
        now = dt.datetime.now(dt.timezone.utc)
        start = now - dt.timedelta(seconds=lookback_s)
        repo = TradeClustersRepository()
        thresholds = await compute_cluster_thresholds_for_tracked_markets(
            cluster_notional_multiplier=cluster_notional_multiplier,
        )
        if not thresholds:
            return 0

        clusters = await repo.list_recent_large_buy_clusters(
            start=start,
            window_s=window_s,
            thresholds=thresholds,
        )
        if not clusters:
            return 0

        rows = [
            {
                "source": r["source"],
                "base_asset": r["base_asset"],
                "quote_asset": r["quote_asset"],
                "window_start_utc": dt.datetime.fromtimestamp(
                    int(r["bucket"]) * window_s,
                    tz=dt.timezone.utc,
                ),
                "window_seconds": window_s,
                "buy_notional_quote": float(r["buy_notional_quote"]),
                "trade_count": int(r["trade_count"]),
                "detected_at": now,
            }
            for r in clusters
        ]
        inserted = await repo.bulk_insert_ignore_conflicts(rows, conflict_constraint="uq_trade_cluster_identity")

        logger.info(
            "trade clusters persisted",
            candidates=len(rows),
            inserted=inserted,
            markets_with_thresholds=len({(t[0], t[1], t[2]) for t in thresholds}),
        )
        return len(rows)
