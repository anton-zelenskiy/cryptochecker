from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class TradeCluster(Base):
    __tablename__ = "trade_clusters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False, default="USDT")

    window_start_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    buy_notional_quote: Mapped[float] = mapped_column(Float, nullable=False)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False)

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
            "window_start_utc",
            "window_seconds",
            name="uq_trade_cluster_identity",
        ),
        Index("ix_trade_clusters_market_time", "base_asset", "quote_asset", "window_start_utc"),
        Index("ix_trade_clusters_detected_at", "detected_at"),
    )
