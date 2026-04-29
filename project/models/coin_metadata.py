from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class CoinMetadata(Base):
    __tablename__ = "coin_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False, default="coingecko")
    coin_id: Mapped[str] = mapped_column(String(128), nullable=False)

    platforms: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("source", "coin_id", name="uq_coin_metadata_identity"),
        Index("ix_coin_metadata_coin", "source", "coin_id"),
        Index("ix_coin_metadata_fetched_at", "fetched_at"),
    )

