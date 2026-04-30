from __future__ import annotations

import datetime as dt

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from project.core.db_session import sessionmanager
from project.models.candles import Candle
from project.models.users import TelegramUser, UserSettings, UserTrackedAsset
from project.models.volatility_events import VolatilityEvent
from project.repositories.indicators import IndicatorSnapshotRepository
from project.services.gemini import SignalSummaryInput, summarize_with_gemini
from project.services.screener_decision import decide_from_indicator_snapshot
from project.services.volatility_big_moves import (
    compute_big_move_metrics,
    floor_time,
    passes_big_move_gate,
)
from project.web.bot import get_bot


logger = structlog.get_logger(__name__)


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

        async with sessionmanager.session() as session:
            res = await session.execute(
                select(UserTrackedAsset.base_asset, UserTrackedAsset.quote_asset)
                .where(UserTrackedAsset.enabled.is_(True))
                .distinct()
            )
            markets = [(str(b), str(q)) for b, q in res.all()]

        if not markets:
            return

        sources = source_preference or ["kucoin", "bybit"]
        indicator_repo = IndicatorSnapshotRepository()
        bot = get_bot()

        try:
            for base, quote in markets:
                latest, prev, source_used = await self._get_latest_two_candles_with_fallback(
                    base=base,
                    quote=quote,
                    timeframe=timeframe,
                    sources=sources,
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
                )
                if not inserted:
                    continue

                subscribers = await self._list_subscribers_for_market(base=base, quote=quote)
                if not subscribers:
                    continue

                snap = await indicator_repo.get_latest(
                    source=source_used, base_asset=base, quote_asset=quote, timeframe=timeframe
                )
                decision = decide_from_indicator_snapshot(snap)
                ai_text = await summarize_with_gemini(
                    SignalSummaryInput(
                        symbol=f"{base}/{quote}",
                        decision=decision.decision,
                        confidence=decision.confidence,
                        rsi_14=decision.rsi_14,
                    )
                )

                direction = "UP" if metrics.pct_change >= 0 else "DOWN"
                base_text = (
                    f"{base}/{quote} {direction} {metrics.pct_change:.2f}% (range {metrics.range_pct:.2f}%)\n"
                    f"decision={decision.decision} confidence={decision.confidence:.2f} rsi14={decision.rsi_14}"
                )
                text = ai_text or base_text

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
    ) -> tuple[Candle | None, Candle | None, str]:
        for src in sources:
            latest, prev = await self._get_latest_two_candles(
                source=src, base=base, quote=quote, timeframe=timeframe
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
    ) -> tuple[Candle | None, Candle | None]:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(Candle)
                .where(Candle.source == source)
                .where(Candle.base_asset == base)
                .where(Candle.quote_asset == quote)
                .where(Candle.timeframe == timeframe)
                .order_by(Candle.open_time_utc.desc())
                .limit(2)
            )
            candles = list(res.scalars().all())
        if not candles:
            return None, None
        if len(candles) == 1:
            return candles[0], None
        return candles[0], candles[1]

    async def _list_subscribers_for_market(self, *, base: str, quote: str) -> list[tuple[int, float]]:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(TelegramUser.telegram_id, UserSettings.volatility_threshold)
                .join(UserSettings, UserSettings.user_id == TelegramUser.id)
                .join(UserTrackedAsset, UserTrackedAsset.user_id == TelegramUser.id)
                .where(UserSettings.notifications_enabled.is_(True))
                .where(UserTrackedAsset.enabled.is_(True))
                .where(UserTrackedAsset.base_asset == base)
                .where(UserTrackedAsset.quote_asset == quote)
            )
            return [(int(tid), float(thr)) for tid, thr in res.all()]

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
        async with sessionmanager.session() as session:
            stmt = insert(VolatilityEvent).values([row])
            stmt = stmt.on_conflict_do_nothing(constraint="uq_volatility_event_dedup")
            res = await session.execute(stmt)
            await session.commit()
            return int(res.rowcount or 0) > 0

