from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)

    decision: Mapped[str] = mapped_column(String(8), nullable=False)  # LONG/SHORT/WAIT (we store non-WAIT)
    bucket_date_utc: Mapped[dt.date] = mapped_column(Date, nullable=False)
    asof_time_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="telegram")
    chat_id: Mapped[int | None] = mapped_column(nullable=True)  # optional: store per-chat send

    __table_args__ = (
        UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "decision",
            "bucket_date_utc",
            "channel",
            name="uq_notification_dedup",
        ),
        Index("ix_notifications_market_time", "base_asset", "quote_asset", "asof_time_utc"),
        Index("ix_notifications_bucket", "bucket_date_utc"),
    )

