from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class ScreenerSnapshot(Base):
    __tablename__ = "screener_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)

    asof_time_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(8), nullable=False, default="1")
    features: Mapped[dict] = mapped_column(JSON, nullable=False)

    decision: Mapped[str] = mapped_column(String(8), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    long_score: Mapped[float] = mapped_column(Float, nullable=False)
    short_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False)

    llm_verdict: Mapped[str | None] = mapped_column(String(24), nullable=True)
    llm_confidence_adjust: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_rationale: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    final_decision: Mapped[str] = mapped_column(String(8), nullable=False)
    final_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    computed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "asof_time_utc",
            name="uq_screener_snapshot_identity",
        ),
        Index("ix_screener_snapshots_market_time", "base_asset", "quote_asset", "computed_at"),
    )


class FvgZone(Base):
    __tablename__ = "fvg_zones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)

    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    zone_low: Mapped[float] = mapped_column(Float, nullable=False)
    zone_high: Mapped[float] = mapped_column(Float, nullable=False)
    formed_at_open_time_utc: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mitigated_at_utc: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "timeframe",
            "formed_at_open_time_utc",
            "direction",
            name="uq_fvg_zone_identity",
        ),
        Index("ix_fvg_zones_market_tf", "base_asset", "quote_asset", "timeframe", "formed_at_open_time_utc"),
    )


class FundamentalsSnapshot(Base):
    __tablename__ = "fundamentals_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    coingecko_id: Mapped[str] = mapped_column(String(128), nullable=False)
    base_symbol: Mapped[str] = mapped_column(String(32), nullable=False)

    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    market_cap_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    fdv_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_volume_24h_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    tvl_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    mcap_to_tvl: Mapped[float | None] = mapped_column(Float, nullable=True)
    fdv_to_tvl: Mapped[float | None] = mapped_column(Float, nullable=True)
    flag_overpriced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flag_undervalued_tvl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tvl_unavailable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    raw_extras: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_fundamentals_coingecko_time", "coingecko_id", "fetched_at"),
        Index("ix_fundamentals_symbol_time", "base_symbol", "fetched_at"),
    )
