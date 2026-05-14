from __future__ import annotations

import datetime as dt

import structlog

from project.core.config import settings
from project.paper_trading.exit import evaluate_exit
from project.paper_trading.stats import format_win_rate_report_message_ru, win_rate_pct
from project.repositories.candles import CandleRepository
from project.repositories.paper_trades import PaperTradeRepository
from project.repositories.screener_snapshots import ScreenerSnapshotRepository
from project.repositories.users import UserSettingsRepository, UserTrackedAssetRepository
from project.web.bot import get_bot
from project.screener.contracts import ScreenerFeaturesV1
from project.screener.risk import select_atr, suggest_trade_levels


logger = structlog.get_logger(__name__)


class PaperTradingService:
    def __init__(
        self,
        *,
        snapshot_repo: ScreenerSnapshotRepository | None = None,
        paper_repo: PaperTradeRepository | None = None,
        candles_repo: CandleRepository | None = None,
    ) -> None:
        self._snapshot_repo = snapshot_repo or ScreenerSnapshotRepository()
        self._paper_repo = paper_repo or PaperTradeRepository()
        self._candles_repo = candles_repo or CandleRepository()

    async def log_win_rate_stats(self) -> None:
        if not settings.PAPER_TRADING_ENABLED:
            return
        agg = await self._paper_repo.aggregate_closed_and_open_counts()
        wr = win_rate_pct(closed_total=int(agg["closed_total"]), wins=int(agg["wins"]))
        logger.info(
            "paper_trades_win_rate",
            open_positions=agg["open_positions"],
            closed_total=agg["closed_total"],
            wins=agg["wins"],
            losses=agg["losses"],
            breakeven=agg["breakeven"],
            win_rate_pct=wr,
            avg_pnl_pct_closed=agg["avg_pnl_pct_closed"],
        )
        if not settings.TELEGRAM_BOT_TOKEN.strip():
            return
        chat_ids = await UserSettingsRepository().list_distinct_notify_telegram_ids_with_tracked_assets()
        if not chat_ids:
            return
        text = format_win_rate_report_message_ru(
            open_positions=int(agg["open_positions"]),
            closed_total=int(agg["closed_total"]),
            wins=int(agg["wins"]),
            losses=int(agg["losses"]),
            breakeven=int(agg["breakeven"]),
            win_rate_pct=wr,
            avg_pnl_pct_closed=float(agg["avg_pnl_pct_closed"])
            if agg["avg_pnl_pct_closed"] is not None
            else None,
        )
        bot = get_bot()
        try:
            for telegram_id in chat_ids:
                try:
                    await bot.send_message(chat_id=telegram_id, text=text)
                except Exception as e:
                    logger.warning(
                        "paper_trades_win_rate telegram send failed",
                        telegram_id=telegram_id,
                        error=str(e),
                    )
        finally:
            await bot.session.close()

    async def paper_trading_tick(self) -> None:
        if not settings.PAPER_TRADING_ENABLED:
            return
        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()
        if not markets:
            return
        for base, quote in sorted(markets):
            try:
                await self._process_market(base_asset=base, quote_asset=quote)
            except Exception as e:
                logger.warning(
                    "paper trading market failed",
                    base_asset=base,
                    quote_asset=quote,
                    error=str(e),
                )

    async def _process_market(self, *, base_asset: str, quote_asset: str) -> None:
        open_trade = await self._paper_repo.get_latest_open_trade_for_market(
            base_asset=base_asset,
            quote_asset=quote_asset,
        )
        snap_row = await self._snapshot_repo.get_latest_for_market(
            base_asset=base_asset,
            quote_asset=quote_asset,
        )

        if open_trade:
            features: ScreenerFeaturesV1 | None = None
            if snap_row is not None and not self._is_snapshot_stale(snap_row):
                features = ScreenerFeaturesV1.model_validate(snap_row.features)
            await self._maybe_close(open_trade=open_trade, snap_row=snap_row, features=features)
            return

        if snap_row is None:
            logger.debug(
                "paper_trading_skip_no_snapshot",
                base_asset=base_asset,
                quote_asset=quote_asset,
            )
            return
        if self._is_snapshot_stale(snap_row):
            logger.debug(
                "paper_trading_skip_stale_snapshot",
                base_asset=base_asset,
                quote_asset=quote_asset,
                computed_at=getattr(snap_row, "computed_at", None),
                max_age_minutes=int(settings.PAPER_TRADING_MAX_SNAPSHOT_AGE_MINUTES),
            )
            return

        features = ScreenerFeaturesV1.model_validate(snap_row.features)
        await self._maybe_open(snap_row=snap_row, features=features)

    def _is_snapshot_stale(self, snap_row: object) -> bool:
        computed_at = getattr(snap_row, "computed_at", None)
        if computed_at is None:
            return True
        now = dt.datetime.now(dt.timezone.utc)
        if computed_at.tzinfo is None:
            computed_at = computed_at.replace(tzinfo=dt.timezone.utc)
        age = now - computed_at
        return age > dt.timedelta(minutes=int(settings.PAPER_TRADING_MAX_SNAPSHOT_AGE_MINUTES))

    async def _maybe_close(
        self,
        *,
        open_trade: object,
        snap_row: object | None,
        features: ScreenerFeaturesV1 | None,
    ) -> bool:
        candles = await self._candles_repo.list_from_open_time_asc(
            source=str(getattr(open_trade, "source")),
            base_asset=str(getattr(open_trade, "base_asset")),
            quote_asset=str(getattr(open_trade, "quote_asset")),
            timeframe=str(settings.PAPER_TRADING_EXIT_SCAN_TIMEFRAME),
            open_time_from_utc=getattr(open_trade, "entry_time_utc"),
            limit=500,
        )
        hit = evaluate_exit(open_trade, candles)
        if hit:
            reason, exit_px, exit_time = hit
            pnl = self._pnl_pct(
                side=str(getattr(open_trade, "side")),
                entry=float(getattr(open_trade, "entry_price")),
                exit_price=float(exit_px),
            )
            await self._paper_repo.close_trade(
                int(getattr(open_trade, "id")),
                exit_time_utc=exit_time,
                exit_price=float(exit_px),
                pnl_pct=float(pnl),
                exit_reason=reason,
            )
            logger.info(
                "paper trade closed",
                base_asset=getattr(open_trade, "base_asset"),
                side=getattr(open_trade, "side"),
                pnl_pct=float(pnl),
                exit_reason=reason,
            )
            return True

        if features is None or snap_row is None:
            return False

        final_d = str(getattr(snap_row, "final_decision"))
        final_c = float(getattr(snap_row, "final_confidence"))
        open_side = str(getattr(open_trade, "side"))
        if self._is_flip_signal(open_side=open_side, final_decision=final_d) and final_c >= float(
            settings.PAPER_TRADING_FLIP_MIN_CONFIDENCE
        ):
            exit_px = features.current_price
            if exit_px is None:
                return False
            exit_time = getattr(snap_row, "computed_at", None) or dt.datetime.now(dt.timezone.utc)
            if getattr(exit_time, "tzinfo", None) is None:
                exit_time = exit_time.replace(tzinfo=dt.timezone.utc)
            pnl = self._pnl_pct(
                side=open_side,
                entry=float(getattr(open_trade, "entry_price")),
                exit_price=float(exit_px),
            )
            await self._paper_repo.close_trade(
                int(getattr(open_trade, "id")),
                exit_time_utc=exit_time,
                exit_price=float(exit_px),
                pnl_pct=float(pnl),
                exit_reason="flip",
            )
            logger.info(
                "paper trade closed",
                base_asset=getattr(open_trade, "base_asset"),
                side=open_side,
                pnl_pct=float(pnl),
                exit_reason="flip",
            )
            return True

        return False

    async def _maybe_open(self, *, snap_row: object, features: ScreenerFeaturesV1) -> None:
        final_d = str(getattr(snap_row, "final_decision"))
        if final_d not in ("LONG", "SHORT"):
            return
        if float(getattr(snap_row, "final_confidence")) < float(settings.PAPER_TRADING_MIN_CONFIDENCE):
            return

        entry_px = features.current_price
        if entry_px is None:
            return

        atr, atr_tf = select_atr(features)
        if atr is None or atr_tf is None:
            return

        try:
            sug = suggest_trade_levels(
                decision=final_d,
                entry=float(entry_px),
                atr=float(atr),
                atr_timeframe=atr_tf,
                fvg=features.fvg,
                min_stop_atr_mult=float(settings.SCREENER_TPSL_MIN_STOP_ATR_MULT),
                min_stop_pct=float(settings.SCREENER_TPSL_MIN_STOP_PCT),
                roundtrip_fee_frac=float(settings.SCREENER_TPSL_ROUNDTRIP_FEE_FRAC),
                roundtrip_slip_frac=float(settings.SCREENER_TPSL_ROUNDTRIP_SLIP_FRAC),
            )
        except Exception:
            return

        entry_time = self._entry_time_utc(features=features, snap_row=snap_row)
        tf = features.current_price_timeframe or settings.PAPER_TRADING_EXIT_SCAN_TIMEFRAME

        trade = await self._paper_repo.open_trade(
            source=str(getattr(snap_row, "source")),
            base_asset=features.base_asset,
            quote_asset=features.quote_asset,
            timeframe=str(tf),
            side=final_d,
            entry_time_utc=entry_time,
            entry_price=float(entry_px),
            hold_candles=None,
            stop_loss=float(sug.stop_loss),
            take_profit=float(sug.take_profit),
            risk_r=float(sug.risk_r),
            atr_used=float(sug.atr_used),
            atr_timeframe=str(sug.atr_timeframe),
            tpsl_method=str(sug.method),
            confidence_at_entry=float(getattr(snap_row, "final_confidence")),
            screener_snapshot_id=int(getattr(snap_row, "id")),
        )
        logger.info(
            "paper trade opened",
            base_asset=features.base_asset,
            side=final_d,
            entry=float(trade.entry_price),
        )

    def _entry_time_utc(self, *, features: ScreenerFeaturesV1, snap_row: object) -> dt.datetime:
        raw = features.current_price_time_utc
        if raw:
            try:
                parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt.timezone.utc)
                return parsed
            except Exception:
                pass
        asof = getattr(snap_row, "asof_time_utc", None)
        if asof is None:
            return dt.datetime.now(dt.timezone.utc)
        if getattr(asof, "tzinfo", None) is None:
            return asof.replace(tzinfo=dt.timezone.utc)
        return asof

    def _is_flip_signal(self, *, open_side: str, final_decision: str) -> bool:
        if final_decision == "LONG" and open_side == "SHORT":
            return True
        return final_decision == "SHORT" and open_side == "LONG"

    def _pnl_pct(self, *, side: str, entry: float, exit_price: float) -> float:
        if entry <= 0:
            return 0.0
        if side == "LONG":
            return (exit_price - entry) / entry * 100.0
        return (entry - exit_price) / entry * 100.0
