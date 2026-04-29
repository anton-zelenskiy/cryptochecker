from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class Candle(Base):
    __tablename__ = "candles"

    open_time_utc: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, primary_key=True
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)  # kucoin/bybit/...
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)  # 1m/5m/1h...

    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)

    volume_base: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_quote: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "timeframe",
            "open_time_utc",
            name="uq_candles_identity",
        ),
        Index(
            "ix_candles_market_tf_time",
            "base_asset",
            "quote_asset",
            "timeframe",
            "open_time_utc",
        ),
        Index("ix_candles_source_tf_time", "source", "timeframe", "open_time_utc"),
    )

