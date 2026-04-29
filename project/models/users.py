from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from project.core.models.base import Base


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)

    settings: Mapped["UserSettings"] = relationship(back_populates="user", uselist=False)
    tracked_assets: Mapped[list["UserTrackedAsset"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id", ondelete="CASCADE"), nullable=False, unique=True)

    notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    volatility_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    app_mode: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    user: Mapped[TelegramUser] = relationship(back_populates="settings")


class UserTrackedAsset(Base):
    __tablename__ = "user_tracked_assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id", ondelete="CASCADE"), nullable=False)

    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False, default="USDT")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    added_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc))

    user: Mapped[TelegramUser] = relationship(back_populates="tracked_assets")

    __table_args__ = (
        UniqueConstraint("user_id", "base_asset", "quote_asset", name="uq_user_tracked_asset"),
        Index("ix_user_tracked_assets_user", "user_id"),
    )

