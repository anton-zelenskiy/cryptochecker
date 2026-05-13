from __future__ import annotations

import datetime as dt

import structlog
from pydantic import BaseModel, ConfigDict

from project.models.candles import Candle
from project.repositories.candles import CandleRepository
from project.repositories.indicators import IndicatorSnapshotRepository
from project.repositories.screener_snapshots import ScreenerSnapshotRepository
from project.repositories.users import UserSettingsRepository, UserTrackedAssetRepository
from project.repositories.volatility_events import VolatilityEventRepository
from project.services.screener_service import fallback_decision_from_indicator_snapshot
from project.web.bot import get_bot


logger = structlog.get_logger(__name__)


class BigMoveMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    pct_change: float
    range_pct: float


def floor_time(ts: dt.datetime, *, seconds: int) -> dt.datetime:
    epoch = int(ts.timestamp())
    floored = epoch - (epoch % seconds)
    return dt.datetime.fromtimestamp(floored, tz=dt.timezone.utc)


def compute_big_move_metrics(
    *, prev_close: float, latest_close: float, latest_high: float, latest_low: float
) -> BigMoveMetrics:
    if prev_close <= 0:
        raise ValueError("prev_close must be > 0")
    pct_change = (latest_close - prev_close) / prev_close * 100.0
    range_pct = (latest_high - latest_low) / prev_close * 100.0
    return BigMoveMetrics(pct_change=float(pct_change), range_pct=float(range_pct))


def passes_big_move_gate(
    metrics: BigMoveMetrics,
    *,
    threshold_pct: float,
    range_multiplier: float = 1.25,
) -> bool:
    return abs(metrics.pct_change) >= threshold_pct or metrics.range_pct >= (threshold_pct * range_multiplier)


def _core_indicators_from_screener_features(
    features: dict | None,
) -> tuple[float | None, float | None, float | None]:
    if not isinstance(features, dict):
        return (None, None, None)
    per = features.get("per_tf_indicators")
    if not isinstance(per, dict):
        return (None, None, None)
    for k in ("1h", "15m", "4h", "5m"):
        block = per.get(k)
        if not isinstance(block, dict) or block.get("rsi_14") is None:
            continue
        rsi = float(block["rsi_14"])
        mh = block.get("macd_hist")
        adx = block.get("adx_14")
        return (
            rsi,
            float(mh) if mh is not None else None,
            float(adx) if adx is not None else None,
        )
    return (None, None, None)


class VolatilityService:
    async def detect_and_notify_big_moves(
        self,
        *,
        timeframe: str = "5m",
        source_preference: list[str] | None = None,
        min_gate_pct: float = 2.0,
    ) -> None:
        tf_seconds = {"5m": 5 * 60}.get(timeframe)
        if tf_seconds is None:
            raise ValueError(f"unsupported timeframe for big moves: {timeframe}")

        now = dt.datetime.now(dt.timezone.utc)
        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()

        if not markets:
            return

        sources = source_preference or ["kucoin", "bybit"]
        indicator_repo = IndicatorSnapshotRepository()
        screener_repo = ScreenerSnapshotRepository()
        candle_repo = CandleRepository()
        event_repo = VolatilityEventRepository()
        settings_repo = UserSettingsRepository()
        bot = get_bot()

        try:
            for base, quote in markets:
                latest, prev, source_used = await self._get_latest_two_candles_with_fallback(
                    base=base,
                    quote=quote,
                    timeframe=timeframe,
                    sources=sources,
                    candle_repo=candle_repo,
                )
                if latest is None or prev is None:
                    continue

                try:
                    metrics = compute_big_move_metrics(
                        prev_close=float(prev.close),
                        latest_close=float(latest.close),
                        latest_high=float(latest.high),
                        latest_low=float(latest.low),
                    )
                except Exception:
                    continue

                if not passes_big_move_gate(metrics, threshold_pct=min_gate_pct):
                    continue

                bucket = floor_time(latest.open_time_utc, seconds=tf_seconds)
                inserted = await self._insert_event_if_new(
                    source=source_used,
                    base=base,
                    quote=quote,
                    timeframe=timeframe,
                    bucket=bucket,
                    metrics=metrics,
                    latest=latest,
                    prev=prev,
                    detected_at=now,
                    repo=event_repo,
                )
                if not inserted:
                    continue

                subscribers = await settings_repo.list_market_subscribers(base_asset=base, quote_asset=quote)
                if not subscribers:
                    continue

                scr = await screener_repo.get_latest_for_market(base_asset=base, quote_asset=quote)
                rsi_for_msg: float | None = None
                macd_for_msg: float | None = None
                adx_for_msg: float | None = None
                if scr and (now - scr.computed_at).total_seconds() < 45 * 60:
                    decision_str = scr.final_decision
                    decision_conf = float(scr.final_confidence)
                    rsi_for_msg, macd_for_msg, adx_for_msg = _core_indicators_from_screener_features(scr.features)
                else:
                    snap = await indicator_repo.get_latest(
                        source=source_used, base_asset=base, quote_asset=quote, timeframe=timeframe
                    )
                    decision_str, decision_conf, rsi_for_msg = fallback_decision_from_indicator_snapshot(snap)
                    macd_for_msg = float(snap.macd_hist) if snap and snap.macd_hist is not None else None
                    adx_for_msg = float(snap.adx_14) if snap and snap.adx_14 is not None else None

                direction = "UP" if metrics.pct_change >= 0 else "DOWN"
                text = (
                    f"Big move: {base}/{quote} {direction} {metrics.pct_change:.2f}% "
                    f"(range {metrics.range_pct:.2f}%)\n"
                    f"Screener context: {decision_str} conf={decision_conf:.2f} "
                    f"rsi14={rsi_for_msg} macd_hist={macd_for_msg} adx14={adx_for_msg}"
                )

                for telegram_id, threshold in subscribers:
                    if not passes_big_move_gate(metrics, threshold_pct=threshold):
                        continue
                    try:
                        await bot.send_message(chat_id=telegram_id, text=text)
                    except Exception as e:
                        logger.warning(
                            "telegram send failed", telegram_id=telegram_id, market=f"{base}/{quote}", error=str(e)
                        )
        finally:
            await bot.session.close()

    async def _get_latest_two_candles_with_fallback(
        self,
        *,
        base: str,
        quote: str,
        timeframe: str,
        sources: list[str],
        candle_repo: CandleRepository,
    ) -> tuple[Candle | None, Candle | None, str]:
        for src in sources:
            latest, prev = await self._get_latest_two_candles(
                source=src,
                base=base,
                quote=quote,
                timeframe=timeframe,
                candle_repo=candle_repo,
            )
            if latest is not None and prev is not None:
                return latest, prev, src
        return None, None, ""

    async def _get_latest_two_candles(
        self,
        *,
        source: str,
        base: str,
        quote: str,
        timeframe: str,
        candle_repo: CandleRepository,
    ) -> tuple[Candle | None, Candle | None]:
        return await candle_repo.get_latest_two(source=source, base_asset=base, quote_asset=quote, timeframe=timeframe)

    async def _insert_event_if_new(
        self,
        *,
        source: str,
        base: str,
        quote: str,
        timeframe: str,
        bucket: dt.datetime,
        metrics,
        latest: Candle,
        prev: Candle,
        detected_at: dt.datetime,
        repo: VolatilityEventRepository,
    ) -> bool:
        row = {
            "source": source,
            "base_asset": base,
            "quote_asset": quote,
            "timeframe": timeframe,
            "event_type": "big_move",
            "bucket_time_utc": bucket,
            "pct_change": float(metrics.pct_change),
            "range_pct": float(metrics.range_pct),
            "volume_quote": float(latest.volume_quote) if latest.volume_quote is not None else None,
            "detected_at": detected_at,
            "payload": {
                "latest_open_time_utc": latest.open_time_utc.isoformat(),
                "latest_close": float(latest.close),
                "prev_close": float(prev.close),
            },
        }
        return await repo.insert_if_new(row, conflict_constraint="uq_volatility_event_dedup")

