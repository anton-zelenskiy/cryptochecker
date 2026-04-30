from __future__ import annotations

import datetime as dt

import structlog

from project.paper_trading.decision import decision_from_rsi
from project.repositories.candles import CandleRepository
from project.repositories.paper_trades import PaperTradeRepository
from project.repositories.users import UserTrackedAssetRepository
from project.services.indicators import compute_rsi_14_snapshot


logger = structlog.get_logger(__name__)


class PaperTradingService:
    async def paper_trading_tick(self, *, timeframe: str = "5m") -> None:
        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()
        if not markets:
            return

        for base, quote in sorted(markets):
            snap = await compute_rsi_14_snapshot(
                source="kucoin",
                base_asset=base,
                quote_asset=quote,
                timeframe=timeframe,
            )
            if not snap or snap.rsi_14 is None:
                continue

            decision, confidence = decision_from_rsi(snap.rsi_14)
            if decision == "WAIT":
                continue

            await self._paper_trade_step(
                source="kucoin",
                base_asset=base,
                quote_asset=quote,
                timeframe=timeframe,
                side=decision,
                confidence=confidence,
            )

    async def _paper_trade_step(
        self,
        *,
        source: str,
        base_asset: str,
        quote_asset: str,
        timeframe: str,
        side: str,
        confidence: float,
        hold_candles: int = 12,
    ) -> None:
        trades_repo = PaperTradeRepository()
        candles_repo = CandleRepository()

        open_trade = await trades_repo.get_latest_open_trade(
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
            timeframe=timeframe,
        )
        if open_trade:
            exit_time = open_trade.entry_time_utc + dt.timedelta(minutes=5 * hold_candles)
            exit_candle = await candles_repo.get_first_after_or_at(
                source=source,
                base_asset=base_asset,
                quote_asset=quote_asset,
                timeframe=timeframe,
                open_time_utc=exit_time,
            )
            if not exit_candle:
                return

            if open_trade.side == "LONG":
                pnl = (exit_candle.close - open_trade.entry_price) / open_trade.entry_price * 100.0
            else:
                pnl = (open_trade.entry_price - exit_candle.close) / open_trade.entry_price * 100.0

            await trades_repo.close_trade(
                open_trade.id,
                exit_time_utc=exit_candle.open_time_utc,
                exit_price=float(exit_candle.close),
                pnl_pct=float(pnl),
            )
            logger.info("paper trade closed", base_asset=base_asset, side=open_trade.side, pnl_pct=float(pnl))
            return

        if confidence < 0.8:
            return

        last_candle = await candles_repo.get_latest(
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
            timeframe=timeframe,
        )
        if not last_candle:
            return

        trade = await trades_repo.open_trade(
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
            timeframe=timeframe,
            side=side,
            entry_time_utc=last_candle.open_time_utc,
            entry_price=float(last_candle.close),
            hold_candles=hold_candles,
        )
        logger.info("paper trade opened", base_asset=base_asset, side=side, entry=float(trade.entry_price))

