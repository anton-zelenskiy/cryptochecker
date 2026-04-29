from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class MarketTrade(Base):
    __tablename__ = "market_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False, default="USDT")

    trade_id: Mapped[str] = mapped_column(String(128), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # "buy" / "sell"
    price: Mapped[float] = mapped_column(Float, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    notional_quote: Mapped[float] = mapped_column(Float, nullable=False)
    trade_time_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "trade_id", name="uq_market_trades_identity"),
        Index("ix_market_trades_market_time", "base_asset", "quote_asset", "trade_time_utc"),
        Index("ix_market_trades_source_time", "source", "trade_time_utc"),
    )

