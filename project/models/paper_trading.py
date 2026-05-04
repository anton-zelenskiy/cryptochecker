from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    side: Mapped[str] = mapped_column(String(8), nullable=False)  # LONG/SHORT

    entry_time_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)

    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_timeframe: Mapped[str | None] = mapped_column(String(8), nullable=True)
    tpsl_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_at_entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    screener_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("screener_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )

    exit_time_utc: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)

    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    hold_candles: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_paper_trades_market_open", "base_asset", "quote_asset", "timeframe", "exit_time_utc"),
    )

