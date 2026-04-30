from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class OrderBookWall(Base):
    __tablename__ = "orderbook_walls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False, default="USDT")

    bucket_time_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    wall_price: Mapped[float] = mapped_column(Float, nullable=False)
    wall_qty: Mapped[float] = mapped_column(Float, nullable=False)
    wall_notional_quote: Mapped[float] = mapped_column(Float, nullable=False)

    best_bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_bid_qty: Mapped[float | None] = mapped_column(Float, nullable=True)

    detected_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "bucket_time_utc",
            "wall_price",
            name="uq_orderbook_wall_identity",
        ),
        Index("ix_orderbook_walls_market_time", "base_asset", "quote_asset", "bucket_time_utc"),
        Index("ix_orderbook_walls_detected_at", "detected_at"),
    )
