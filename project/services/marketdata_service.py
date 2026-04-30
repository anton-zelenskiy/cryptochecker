from __future__ import annotations

import datetime as dt
from collections import Counter

import structlog

from project.marketdata.dto import NormalizedMarket
from project.marketdata.providers.bybit_candles import BybitCandleProvider
from project.marketdata.providers.kucoin_candles import KuCoinCandleProvider
from project.repositories.candles import CandleRepository
from project.repositories.users import UserTrackedAssetRepository


logger = structlog.get_logger(__name__)


class MarketDataService:
    async def ingest_tracked_candles(self, *, timeframe: str = "5m", lookback_hours: int = 3) -> None:
        log = logger.bind(task="ingest_tracked_candles")
        started_at = dt.datetime.now(dt.timezone.utc)

        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()
        log.info("tracked candles ingest started", users_markets=len(markets))
        if not markets:
            log.info("no tracked markets; skipping")
            return

        end = dt.datetime.now(dt.timezone.utc)
        start = end - dt.timedelta(hours=lookback_hours)
        log = log.bind(markets=len(markets), timeframe=timeframe, start=start.isoformat(), end=end.isoformat())

        providers = [KuCoinCandleProvider(), BybitCandleProvider()]
        candle_repo = CandleRepository()

        rows: list[dict] = []
        fetched = 0
        empty_fetches = 0
        per_source_counts: Counter[str] = Counter()

        for base, quote in sorted(markets):
            market = NormalizedMarket(base_asset=base, quote_asset=quote)
            for p in providers:
                try:
                    candles = await p.fetch_ohlcv(market, timeframe, start, end)
                except Exception as e:
                    log.warning("candle fetch failed", source=p.source, market=market.pair, error=str(e))
                    continue
                fetched += 1
                if not candles:
                    empty_fetches += 1
                    log.info("no candles fetched", source=p.source, market=market.pair)
                    continue

                per_source_counts[p.source] += len(candles)
                log.info(
                    "candles fetched",
                    source=p.source,
                    market=market.pair,
                    candles=len(candles),
                    first_open_time_utc=candles[0].open_time_utc.isoformat(),
                    last_open_time_utc=candles[-1].open_time_utc.isoformat(),
                )
                for c in candles:
                    rows.append(
                        {
                            "source": c.source,
                            "base_asset": c.market.base_asset,
                            "quote_asset": c.market.quote_asset,
                            "timeframe": c.timeframe,
                            "open_time_utc": c.open_time_utc,
                            "open": c.open,
                            "high": c.high,
                            "low": c.low,
                            "close": c.close,
                            "volume_base": c.volume_base,
                            "volume_quote": c.volume_quote,
                        }
                    )

        if not rows:
            log.info("no candle rows built; skipping db write", fetch_attempts=fetched, empty_fetches=empty_fetches)
            return

        inserted = await candle_repo.bulk_insert_ignore_conflicts(rows, conflict_constraint="uq_candles_identity")
        elapsed_ms = int((dt.datetime.now(dt.timezone.utc) - started_at).total_seconds() * 1000)
        log.info(
            "tracked candles ingest finished",
            fetch_attempts=fetched,
            empty_fetches=empty_fetches,
            rows=len(rows),
            inserted=inserted,
            per_source=dict(per_source_counts),
            elapsed_ms=elapsed_ms,
        )

