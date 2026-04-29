from __future__ import annotations

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from project.core.models.base import Base


class CatalogCoin(Base):
    __tablename__ = "catalog_coins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    coingecko_id: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    market_cap_rank: Mapped[int | None] = mapped_column(nullable=True)
    is_stablecoin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("coingecko_id", name="uq_catalog_coingecko_id"),
        Index("ix_catalog_symbol", "symbol"),
        Index("ix_catalog_rank", "market_cap_rank"),
    )

