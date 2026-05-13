from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

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

    async def get_latest_open_trade_for_market(
        self,
        *,
        base_asset: str,
        quote_asset: str,
    ) -> PaperTrade | None:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(PaperTrade)
                .where(PaperTrade.base_asset == base_asset)
                .where(PaperTrade.quote_asset == quote_asset)
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
        exit_reason: str | None = None,
    ) -> None:
        async with sessionmanager.session() as session:
            res = await session.execute(select(PaperTrade).where(PaperTrade.id == trade_id))
            trade = res.scalar_one_or_none()
            if trade is None:
                return
            trade.exit_time_utc = exit_time_utc
            trade.exit_price = float(exit_price)
            trade.pnl_pct = float(pnl_pct)
            if exit_reason is not None:
                trade.exit_reason = exit_reason
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
        hold_candles: int | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        risk_r: float | None = None,
        atr_used: float | None = None,
        atr_timeframe: str | None = None,
        tpsl_method: str | None = None,
        confidence_at_entry: float | None = None,
        screener_snapshot_id: int | None = None,
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
                hold_candles=hold_candles,
                stop_loss=float(stop_loss) if stop_loss is not None else None,
                take_profit=float(take_profit) if take_profit is not None else None,
                risk_r=float(risk_r) if risk_r is not None else None,
                atr_used=float(atr_used) if atr_used is not None else None,
                atr_timeframe=atr_timeframe,
                tpsl_method=tpsl_method,
                confidence_at_entry=float(confidence_at_entry) if confidence_at_entry is not None else None,
                screener_snapshot_id=screener_snapshot_id,
            )
            session.add(trade)
            await session.commit()
            await session.refresh(trade)
            return trade

    async def aggregate_closed_and_open_counts(self) -> dict[str, int | float | None]:
        async with sessionmanager.session() as session:
            open_positions = int(
                await session.scalar(select(func.count()).where(PaperTrade.exit_time_utc.is_(None))) or 0
            )
            closed_total = int(
                await session.scalar(select(func.count()).where(PaperTrade.exit_time_utc.is_not(None))) or 0
            )
            wins = int(
                await session.scalar(
                    select(func.count()).where(
                        PaperTrade.exit_time_utc.is_not(None),
                        PaperTrade.pnl_pct > 0,
                    )
                )
                or 0
            )
            losses = int(
                await session.scalar(
                    select(func.count()).where(
                        PaperTrade.exit_time_utc.is_not(None),
                        PaperTrade.pnl_pct < 0,
                    )
                )
                or 0
            )
            breakeven = int(
                await session.scalar(
                    select(func.count()).where(
                        PaperTrade.exit_time_utc.is_not(None),
                        PaperTrade.pnl_pct == 0,
                    )
                )
                or 0
            )
            avg_pnl = await session.scalar(
                select(func.avg(PaperTrade.pnl_pct)).where(PaperTrade.exit_time_utc.is_not(None))
            )
        return {
            "open_positions": open_positions,
            "closed_total": closed_total,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "avg_pnl_pct_closed": float(avg_pnl) if avg_pnl is not None else None,
        }
