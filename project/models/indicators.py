from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class IndicatorSnapshot(Base):
    __tablename__ = "indicator_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    asof_time_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    rsi_14: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "timeframe",
            "asof_time_utc",
            name="uq_indicator_snapshot_identity",
        ),
        Index("ix_indicator_snapshots_market_tf_time", "base_asset", "quote_asset", "timeframe", "asof_time_utc"),
    )

