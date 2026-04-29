from __future__ import annotations

import asyncio
import datetime as dt

import structlog

from project.repositories.users import TelegramUserRepository, UserTrackedAssetRepository
from project.services.indicators import compute_rsi_14_snapshot
from project.core.db_session import sessionmanager
from project.models.candles import Candle
from project.models.paper_trading import PaperTrade
from project.paper_trading.decision import decision_from_rsi
from sqlalchemy import select

from project.celery_app import celery_app


logger = structlog.get_logger(__name__)


@celery_app.task(name="project.tasks.paper_trading.paper_trading_tick")
def paper_trading_tick() -> None:
    """
    Placeholder for paper trading simulation tick.

    Implemented fully in later steps (signals, entries, exits, PnL persistence).
    """
    asyncio.run(_paper_trading_tick())


async def _paper_trading_tick() -> None:
    user_repo = TelegramUserRepository()
    tracked_repo = UserTrackedAssetRepository()

    users = await user_repo.get_all()
    markets: set[tuple[str, str]] = set()
    for u in users:
        assets = await tracked_repo.list_enabled_assets(u.id)
        for a in assets:
            markets.add((a.base_asset, a.quote_asset))

    # Best-effort: compute RSI snapshots for KuCoin 5m candles and open/close paper trades.
    for base, quote in sorted(markets):
        snap = await compute_rsi_14_snapshot(
            source="kucoin",
            base_asset=base,
            quote_asset=quote,
            timeframe="5m",
        )
        if not snap or snap.rsi_14 is None:
            continue

        decision, confidence = decision_from_rsi(snap.rsi_14)
        if decision == "WAIT":
            continue

        await _paper_trade_step(
            source="kucoin",
            base_asset=base,
            quote_asset=quote,
            timeframe="5m",
            side=decision,
            confidence=confidence,
        )


async def _paper_trade_step(
    *,
    source: str,
    base_asset: str,
    quote_asset: str,
    timeframe: str,
    side: str,
    confidence: float,
    hold_candles: int = 12,
) -> None:
    # 1) If there is an open trade, try to close when hold_candles passed.
    async with sessionmanager.session() as session:
        res = await session.execute(
            select(PaperTrade)
            .where(PaperTrade.source == source)
            .where(PaperTrade.base_asset == base_asset)
            .where(PaperTrade.quote_asset == quote_asset)
            .where(PaperTrade.timeframe == timeframe)
            .where(PaperTrade.exit_time_utc.is_(None))
            .order_by(PaperTrade.entry_time_utc.desc())
            .limit(1)
        )
        open_trade = res.scalar_one_or_none()

        if open_trade:
            # find exit candle (entry_time + hold_candles * tf)
            exit_time = open_trade.entry_time_utc + dt.timedelta(minutes=5 * hold_candles)
            cres = await session.execute(
                select(Candle)
                .where(Candle.source == source)
                .where(Candle.base_asset == base_asset)
                .where(Candle.quote_asset == quote_asset)
                .where(Candle.timeframe == timeframe)
                .where(Candle.open_time_utc >= exit_time)
                .order_by(Candle.open_time_utc.asc())
                .limit(1)
            )
            exit_candle = cres.scalar_one_or_none()
            if not exit_candle:
                return

            open_trade.exit_time_utc = exit_candle.open_time_utc
            open_trade.exit_price = exit_candle.close
            if open_trade.side == "LONG":
                pnl = (exit_candle.close - open_trade.entry_price) / open_trade.entry_price * 100.0
            else:
                pnl = (open_trade.entry_price - exit_candle.close) / open_trade.entry_price * 100.0
            open_trade.pnl_pct = float(pnl)
            await session.commit()
            logger.info(
                "paper trade closed",
                base_asset=base_asset,
                side=open_trade.side,
                pnl_pct=open_trade.pnl_pct,
            )
            return

        # 2) No open trade -> open new if confidence is high enough.
        if confidence < 0.8:
            return

        cres = await session.execute(
            select(Candle)
            .where(Candle.source == source)
            .where(Candle.base_asset == base_asset)
            .where(Candle.quote_asset == quote_asset)
            .where(Candle.timeframe == timeframe)
            .order_by(Candle.open_time_utc.desc())
            .limit(1)
        )
        last_candle = cres.scalar_one_or_none()
        if not last_candle:
            return

        trade = PaperTrade(
            source=source,
            base_asset=base_asset,
            quote_asset=quote_asset,
            timeframe=timeframe,
            side=side,
            entry_time_utc=last_candle.open_time_utc,
            entry_price=last_candle.close,
            hold_candles=hold_candles,
        )
        session.add(trade)
        await session.commit()
        logger.info("paper trade opened", base_asset=base_asset, side=side, entry=trade.entry_price)

