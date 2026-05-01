from __future__ import annotations

import datetime as dt

import structlog

from project.core.config import settings
from project.models.candles import Candle
from project.models.indicators import IndicatorSnapshot
from project.repositories.catalog import CatalogRepository
from project.repositories.candles import CandleRepository
from project.repositories.fvg_zones import FvgZoneRepository
from project.repositories.notifications import NotificationRepository
from project.repositories.orderbook_walls import OrderBookWallRepository
from project.repositories.screener_snapshots import ScreenerSnapshotRepository
from project.repositories.trade_clusters import TradeClustersRepository
from project.repositories.users import UserSettingsRepository, UserTrackedAssetRepository
from project.screener.contracts import (
    FvgNearbyFeature,
    FundamentalsFeature,
    MicrostructureFeature,
    PerTimeframeIndicators,
    ScreenerFeaturesV1,
    ScreenerFinalPayload,
    TrendBias,
    TrendSwingFeature,
)
from project.screener.risk import select_atr, suggest_trade_levels
from project.screener.fvg_detect import detect_fvgs, distance_pct_to_zone_mid
from project.screener.scoring import apply_llm_adjustment, score_screener
from project.screener.trend_structure import aggregate_bias, compute_trend_swing_feature
from project.screener.volume_regime import CandleOHLCV, compute_volume_regime
from project.services.fundamentals_snapshot_service import fetch_and_store_fundamentals_if_stale
from project.services.gemini import SignalSummaryInput, recheck_screener_with_gemini, summarize_with_gemini
from project.services.indicators import compute_indicator_bundle_snapshot
from project.web.bot import get_bot


logger = structlog.get_logger(__name__)

TF_HIGHER = ("4h", "1d")
TF_LOWER = ("15m", "1h")
TF_ALL = ("15m", "1h", "4h", "1d")
SOURCES_TRY = ("kucoin", "bybit")
PRICE_TF_PREFERENCE = ("5m", "15m", "1h")

def _snap_to_per_tf(s: IndicatorSnapshot, tf: str) -> PerTimeframeIndicators:
    return PerTimeframeIndicators(
        timeframe=tf,
        rsi_14=s.rsi_14,
        ema_20=s.ema_20,
        ema_50=s.ema_50,
        ema_200=s.ema_200,
        macd=s.macd,
        macd_signal=s.macd_signal,
        macd_hist=s.macd_hist,
        atr_14=s.atr_14,
        adx_14=s.adx_14,
        bb_upper=s.bb_upper,
        bb_mid=s.bb_mid,
        bb_lower=s.bb_lower,
        mfi_14=s.mfi_14,
        obv=s.obv,
        stochrsi_k=s.stochrsi_k,
        stochrsi_d=s.stochrsi_d,
    )


def _candles_to_ohlcv(candles: list[Candle]) -> list[CandleOHLCV]:
    return [
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


async def _resolve_source(*, base: str, quote: str) -> str | None:
    repo = CandleRepository()
    for src in SOURCES_TRY:
        c = await repo.get_latest(source=src, base_asset=base, quote_asset=quote, timeframe="1h")
        if c:
            return src
    return None


async def _resolve_current_price(
    *,
    candle_repo: CandleRepository,
    source: str,
    base_asset: str,
    quote_asset: str,
) -> tuple[float | None, dt.datetime | None, str | None]:
    for tf in PRICE_TF_PREFERENCE:
        c = await candle_repo.get_latest(
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
            timeframe=tf,
        )
        if c is None:
            continue
        try:
            return float(c.close), c.open_time_utc, tf
        except Exception:
            continue
    return None, None, None


def fallback_decision_from_indicator_snapshot(
    snap: IndicatorSnapshot | None,
) -> tuple[str, float, float | None]:
    if snap is None or snap.rsi_14 is None:
        return "WAIT", 0.0, None
    rsi = float(snap.rsi_14)
    if rsi <= 30:
        return "LONG", min(1.0, (30 - rsi) / 30 + 0.5), rsi
    if rsi >= 70:
        return "SHORT", min(1.0, (rsi - 70) / 30 + 0.5), rsi
    return "WAIT", 0.2, rsi


class ScreenerService:
    async def compute_and_persist_for_market(
        self,
        *,
        base_asset: str,
        quote_asset: str,
        run_llm_recheck: bool | None = None,
    ) -> ScreenerFinalPayload | None:
        source = await _resolve_source(base=base_asset, quote=quote_asset)
        if not source:
            logger.info("screener skip no candles", base=base_asset, quote=quote_asset)
            return None

        candle_repo = CandleRepository()
        per_tf_indicators: dict[str, PerTimeframeIndicators] = {}
        per_tf_trend: dict[str, TrendSwingFeature] = {}

        current_price, current_price_time, current_price_tf = await _resolve_current_price(
            candle_repo=candle_repo,
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
        )

        for tf in TF_ALL:
            snap = await compute_indicator_bundle_snapshot(
                source=source,
                base_asset=base_asset,
                quote_asset=quote_asset,
                timeframe=tf,
                limit=400,
            )
            if not snap:
                continue
            per_tf_indicators[tf] = _snap_to_per_tf(snap, tf)
            candles = await candle_repo.list_latest_n(
                source=source,
                base_asset=base_asset,
                quote_asset=quote_asset,
                timeframe=tf,
                limit=220,
            )
            if len(candles) < 20:
                continue
            candles.sort(key=lambda x: x.open_time_utc)
            highs = [float(c.high) for c in candles]
            lows = [float(c.low) for c in candles]
            closes = [float(c.close) for c in candles]
            per_tf_trend[tf] = compute_trend_swing_feature(
                timeframe=tf,
                highs=highs,
                lows=lows,
                closes=closes,
                ema20=snap.ema_20,
                ema50=snap.ema_50,
                ema200=snap.ema_200,
            )

        if not per_tf_indicators:
            return None

        vol_candles = await candle_repo.list_latest_n(
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
            timeframe="1h",
            limit=900,
        )
        vol_feat = compute_volume_regime(_candles_to_ohlcv(vol_candles), lookback_days=14)

        higher_tf_trend = {k: v for k, v in per_tf_trend.items() if k in TF_HIGHER}
        lower_tf_trend = {k: v for k, v in per_tf_trend.items() if k in TF_LOWER}
        higher_bias: TrendBias = aggregate_bias([t.bias for t in higher_tf_trend.values()])
        lower_bias: TrendBias = aggregate_bias([t.bias for t in lower_tf_trend.values()])

        fvg_repo = FvgZoneRepository()
        fvg_feat, fvg_long, fvg_short = await self._process_fvg(
            candle_repo=candle_repo,
            fvg_repo=fvg_repo,
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
        )

        fund_feat = await self._load_fundamentals_feature(base_asset=base_asset)

        micro = await self._microstructure(base_asset=base_asset, quote_asset=quote_asset)

        det = score_screener(
            higher_tf_trends=higher_tf_trend,
            lower_tf_trends=lower_tf_trend,
            indicators_by_tf=per_tf_indicators,
            volume=vol_feat,
            fundamentals=fund_feat,
            microstructure=micro,
            fvg_aligns_long=fvg_long,
            fvg_aligns_short=fvg_short,
        )

        asof_times: list[dt.datetime] = []
        for tf in TF_ALL:
            c = await candle_repo.get_latest(
                source=source, base_asset=base_asset, quote_asset=quote_asset, timeframe=tf
            )
            if c is not None:
                asof_times.append(c.open_time_utc)
        asof = max(asof_times) if asof_times else dt.datetime.now(dt.timezone.utc)

        features = ScreenerFeaturesV1(
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
            asof_time_utc=asof.isoformat(),
            current_price=current_price,
            current_price_time_utc=current_price_time.isoformat() if current_price_time else None,
            current_price_timeframe=current_price_tf,
            per_tf_indicators={k: v for k, v in per_tf_indicators.items()},
            per_tf_trend={k: v for k, v in per_tf_trend.items()},
            volume=vol_feat,
            higher_tf_bias=higher_bias,
            lower_tf_bias=lower_bias,
            fvg=fvg_feat,
            fundamentals=fund_feat,
            microstructure=micro,
        )

        llm = None
        do_llm = settings.SCREENER_LLM_RECHECK_ENABLED if run_llm_recheck is None else run_llm_recheck
        if do_llm:
            llm = await recheck_screener_with_gemini(
                features_json=features.model_dump(mode="json"),
                deterministic=det.model_dump(mode="json"),
            )

        final_d, final_c = det.decision, det.confidence
        if llm:
            final_d, final_c = apply_llm_adjustment(
                det.decision, det.confidence, llm.verdict, llm.confidence_adjust
            )

        snap_repo = ScreenerSnapshotRepository()
        await snap_repo.upsert_snapshot(
            {
                "source": source,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "asof_time_utc": asof,
                "feature_version": features.version,
                "features": features.model_dump(mode="json"),
                "decision": det.decision,
                "confidence": float(det.confidence),
                "long_score": float(det.long_score),
                "short_score": float(det.short_score),
                "risk_score": float(det.risk_score),
                "reasons": det.reasons,
                "llm_verdict": llm.verdict if llm else None,
                "llm_confidence_adjust": float(llm.confidence_adjust) if llm else None,
                "llm_rationale": llm.rationale if llm else None,
                "final_decision": final_d,
                "final_confidence": float(final_c),
                "computed_at": dt.datetime.now(dt.timezone.utc),
            }
        )

        return ScreenerFinalPayload(
            deterministic=det,
            llm=llm,
            final_decision=final_d,
            final_confidence=final_c,
        )

    async def notify_market_if_needed(
        self,
        *,
        base_asset: str,
        quote_asset: str,
        features: ScreenerFeaturesV1,
        payload: ScreenerFinalPayload,
    ) -> int:
        if not settings.SCREENER_NOTIFICATIONS_ENABLED:
            return 0
        if payload.final_decision == "WAIT":
            return 0
        if payload.final_confidence < float(settings.SCREENER_NOTIFY_MIN_CONFIDENCE):
            return 0

        # DB dedup: store a single notification marker for market+decision+day.
        # If it already exists, skip sending (prevents spam and enables compute skipping).
        asof_dt = dt.datetime.fromisoformat(features.asof_time_utc)
        bucket_date = asof_dt.date()
        nrepo = NotificationRepository()
        inserted = await nrepo.insert_ignore(
            {
                "source": features.source,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "decision": payload.final_decision,
                "bucket_date_utc": bucket_date,
                "asof_time_utc": asof_dt,
                "channel": "telegram",
                "chat_id": None,
            }
        )
        if inserted <= 0:
            return 0

        settings_repo = UserSettingsRepository()
        subscribers = await settings_repo.list_market_subscribers(
            base_asset=base_asset, quote_asset=quote_asset
        )
        if not subscribers:
            return 0

        reasons = payload.deterministic.reasons[:12]

        notes: dict[str, str] = {}
        if features.current_price is not None:
            notes["price"] = f"{features.current_price:g}"
            if features.current_price_timeframe:
                notes["price_tf"] = str(features.current_price_timeframe)
            if features.current_price_time_utc:
                notes["price_time_utc"] = str(features.current_price_time_utc)

        tpsl_line = ""
        if payload.final_decision in ("LONG", "SHORT") and features.current_price is not None:
            atr, atr_tf = select_atr(features)
            if atr is not None and atr_tf is not None:
                try:
                    sug = suggest_trade_levels(
                        decision=payload.final_decision,
                        entry=float(features.current_price),
                        atr=float(atr),
                        atr_timeframe=atr_tf,
                        fvg=features.fvg,
                    )
                    notes["sl"] = f"{sug.stop_loss:g}"
                    notes["tp"] = f"{sug.take_profit:g}"
                    notes["risk_r"] = f"{sug.risk_r:g}"
                    notes["atr"] = f"{sug.atr_used:g}"
                    notes["atr_tf"] = str(sug.atr_timeframe)
                    notes["tpsl_method"] = str(sug.method)
                    tpsl_line = (
                        f"price={sug.entry:g} SL={sug.stop_loss:g} TP={sug.take_profit:g} "
                        f"(R={sug.risk_r:g}, ATR({sug.atr_timeframe})={sug.atr_used:g}, {sug.method})"
                    )
                except Exception:
                    tpsl_line = ""

        ai_text = await summarize_with_gemini(
            SignalSummaryInput(
                symbol=f"{base_asset}/{quote_asset}",
                decision=payload.final_decision,
                confidence=float(payload.final_confidence),
                rsi_14=features.per_tf_indicators.get("1h", None).rsi_14
                if "1h" in features.per_tf_indicators
                else None,
                notes=notes or None,
                screener_final_decision=payload.final_decision,
                screener_final_confidence=float(payload.final_confidence),
                screener_reasons=[str(x) for x in reasons],
                llm_verdict=payload.llm.verdict if payload.llm else None,
                llm_rationale=payload.llm.rationale if payload.llm else None,
            )
        )
        text = ai_text or (
            f"{base_asset}/{quote_asset}\n"
            f"decision={payload.final_decision} confidence={payload.final_confidence:.2f}\n"
            + "\n".join(f"- {r}" for r in reasons)
            + (f"\n{tpsl_line}" if tpsl_line else "")
        )

        bot = get_bot()
        sent = 0
        try:
            for telegram_id, _thr in subscribers:
                try:
                    await bot.send_message(chat_id=telegram_id, text=text)
                    sent += 1
                except Exception as e:
                    logger.warning(
                        "telegram send failed",
                        telegram_id=telegram_id,
                        market=f"{base_asset}/{quote_asset}",
                        error=str(e),
                    )
        finally:
            await bot.session.close()

        return sent

    async def _process_fvg(
        self,
        *,
        candle_repo: CandleRepository,
        fvg_repo: FvgZoneRepository,
        source: str,
        base_asset: str,
        quote_asset: str,
        timeframe: str = "15m",
    ) -> tuple[FvgNearbyFeature | None, bool, bool]:
        candles = await candle_repo.list_latest_n(
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
            timeframe=timeframe,
            limit=160,
        )
        if len(candles) < 5:
            return None, False, False
        candles.sort(key=lambda c: c.open_time_utc)
        times = [c.open_time_utc for c in candles]
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        closes = [float(c.close) for c in candles]
        last_close = closes[-1]
        now = dt.datetime.now(dt.timezone.utc)

        fvgs = detect_fvgs(times, highs, lows, closes)
        for f in fvgs[-12:]:
            await fvg_repo.insert_ignore(
                {
                    "source": source,
                    "base_asset": base_asset,
                    "quote_asset": quote_asset,
                    "timeframe": timeframe,
                    "direction": f.direction,
                    "zone_low": f.zone_low,
                    "zone_high": f.zone_high,
                    "formed_at_open_time_utc": f.middle_open_time_utc,
                }
            )

        open_zones = await fvg_repo.list_unmitigated(
            source=source, base_asset=base_asset, quote_asset=quote_asset, timeframe=timeframe
        )
        for z in open_zones:
            if z.direction == "bull" and last_close <= z.zone_low:
                await fvg_repo.set_mitigated(z.id, at=now)
            elif z.direction == "bear" and last_close >= z.zone_high:
                await fvg_repo.set_mitigated(z.id, at=now)

        open_zones = await fvg_repo.list_unmitigated(
            source=source, base_asset=base_asset, quote_asset=quote_asset, timeframe=timeframe
        )
        if not open_zones:
            return None, False, False

        nearest = min(
            open_zones,
            key=lambda z: distance_pct_to_zone_mid(last_close, z.zone_low, z.zone_high),
        )
        dist = distance_pct_to_zone_mid(last_close, nearest.zone_low, nearest.zone_high)
        feat = FvgNearbyFeature(
            timeframe=timeframe,
            direction=nearest.direction,
            zone_low=nearest.zone_low,
            zone_high=nearest.zone_high,
            distance_pct_to_mid=dist,
            is_unfilled=True,
        )
        aligns_long = nearest.direction == "bull" and dist < 2.5 and last_close >= nearest.zone_low
        aligns_short = nearest.direction == "bear" and dist < 2.5 and last_close <= nearest.zone_high
        return feat, aligns_long, aligns_short

    async def _load_fundamentals_feature(self, *, base_asset: str) -> FundamentalsFeature | None:
        cat = await CatalogRepository().get_first_by_symbol(source="coingecko", symbol=base_asset)
        if not cat:
            return FundamentalsFeature(coingecko_id=None, tvl_unavailable=True)
        data = await fetch_and_store_fundamentals_if_stale(
            coingecko_id=cat.coingecko_id,
            base_symbol=base_asset,
        )
        if not data:
            return FundamentalsFeature(coingecko_id=cat.coingecko_id, tvl_unavailable=True)
        return FundamentalsFeature(
            coingecko_id=data["coingecko_id"],
            market_cap_usd=data.get("market_cap_usd"),
            fdv_usd=data.get("fdv_usd"),
            total_volume_24h_usd=data.get("total_volume_24h_usd"),
            tvl_usd=data.get("tvl_usd"),
            mcap_to_tvl=data.get("mcap_to_tvl"),
            fdv_to_tvl=data.get("fdv_to_tvl"),
            flag_overpriced=bool(data.get("flag_overpriced")),
            flag_undervalued_tvl=bool(data.get("flag_undervalued_tvl")),
            tvl_unavailable=bool(data.get("tvl_unavailable")),
        )

    async def _microstructure(self, *, base_asset: str, quote_asset: str) -> MicrostructureFeature:
        since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=45)
        tc = await TradeClustersRepository().count_recent_for_market(
            base_asset=base_asset, quote_asset=quote_asset, since=since
        )
        ob = await OrderBookWallRepository().count_recent_for_market(
            base_asset=base_asset, quote_asset=quote_asset, since=since
        )
        return MicrostructureFeature(
            large_buy_cluster_recent=tc > 0,
            support_wall_recent=ob > 0,
        )

    async def run_for_all_tracked(self, *, run_llm_recheck: bool | None = None) -> int:
        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()
        n = 0
        for base, quote in sorted(markets):
            try:
                r = await self.compute_and_persist_for_market(
                    base_asset=base, quote_asset=quote, run_llm_recheck=run_llm_recheck
                )
                if r:
                    n += 1
            except Exception as e:
                logger.warning("screener market failed", base=base, quote=quote, error=str(e))
        return n

    async def run_for_all_tracked_and_notify(self, *, run_llm_recheck: bool | None = None) -> int:
        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()
        processed = 0
        for base, quote in sorted(markets):
            try:
                # If we already have a non-WAIT decision that was sent recently,
                # skip recomputing this market to reduce API load.
                prev = await ScreenerSnapshotRepository().get_latest_for_market(base_asset=base, quote_asset=quote)
                if prev and prev.final_decision in ("LONG", "SHORT"):
                    lookback = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
                        hours=int(settings.SCREENER_SIGNAL_DEDUP_TTL_HOURS)
                    )
                    exists = await NotificationRepository().get_latest_for_market_since(
                        source=str(prev.source),
                        base_asset=base,
                        quote_asset=quote,
                        decision=str(prev.final_decision),
                        channel="telegram",
                        since=lookback,
                    )
                    if exists:
                        continue

                result = await self.compute_and_persist_for_market(
                    base_asset=base,
                    quote_asset=quote,
                    run_llm_recheck=run_llm_recheck,
                )
                if not result:
                    continue

                # Build lightweight features view for notify (reuse last snapshot in DB would be extra query).
                # We already computed features inside compute_and_persist_for_market, but it doesn’t return them,
                # so we read the persisted snapshot once.
                snap = await ScreenerSnapshotRepository().get_latest_for_market(
                    base_asset=base, quote_asset=quote
                )
                if not snap:
                    continue
                features = ScreenerFeaturesV1.model_validate(snap.features)
                await self.notify_market_if_needed(
                    base_asset=base,
                    quote_asset=quote,
                    features=features,
                    payload=result,
                )
                processed += 1
            except Exception as e:
                logger.warning("screener market failed", base=base, quote=quote, error=str(e))
        return processed
