from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class VolatilityEvent(Base):
    __tablename__ = "volatility_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False, default="USDT")
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    event_type: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. "big_move"
    bucket_time_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    pct_change: Mapped[float] = mapped_column(Float, nullable=False)
    range_pct: Mapped[float] = mapped_column(Float, nullable=False)
    volume_quote: Mapped[float | None] = mapped_column(Float, nullable=True)

    detected_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "timeframe",
            "event_type",
            "bucket_time_utc",
            name="uq_volatility_event_dedup",
        ),
        Index(
            "ix_volatility_events_market_time",
            "base_asset",
            "quote_asset",
            "timeframe",
            "bucket_time_utc",
        ),
        Index("ix_volatility_events_detected_at", "detected_at"),
    )

