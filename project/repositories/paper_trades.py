from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from project.core.db_session import sessionmanager
from project.models.paper_trading import PaperTrade


class PaperTradeRepository:
    async def get_latest_open_trade(
        self,
        *,
        source: str,
        base_asset: str,
        quote_asset: str,
        timeframe: str,
    ) -> PaperTrade | None:
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
            return res.scalar_one_or_none()

    async def close_trade(
        self,
        trade_id: int,
        *,
        exit_time_utc: dt.datetime,
        exit_price: float,
        pnl_pct: float,
    ) -> None:
        async with sessionmanager.session() as session:
            res = await session.execute(select(PaperTrade).where(PaperTrade.id == trade_id))
            trade = res.scalar_one_or_none()
            if trade is None:
                return
            trade.exit_time_utc = exit_time_utc
            trade.exit_price = float(exit_price)
            trade.pnl_pct = float(pnl_pct)
            await session.commit()

    async def open_trade(
        self,
        *,
        source: str,
        base_asset: str,
        quote_asset: str,
        timeframe: str,
        side: str,
        entry_time_utc: dt.datetime,
        entry_price: float,
        hold_candles: int,
    ) -> PaperTrade:
        async with sessionmanager.session() as session:
            trade = PaperTrade(
                source=source,
                base_asset=base_asset,
                quote_asset=quote_asset,
                timeframe=timeframe,
                side=side,
                entry_time_utc=entry_time_utc,
                entry_price=float(entry_price),
                hold_candles=int(hold_candles),
            )
            session.add(trade)
            await session.commit()
            await session.refresh(trade)
            return trade

