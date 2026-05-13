from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from project.core.repository import BaseRepository
from project.models.users import TelegramUser, UserSettings, UserTrackedAsset


class TelegramUserRepository(BaseRepository[TelegramUser]):
    def __init__(self) -> None:
        super().__init__(TelegramUser)

    async def get_or_create(self, telegram_id: int) -> TelegramUser:
        async with self._sessionmanager.session() as session:
            res = await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
            )
            user = res.scalar_one_or_none()
            if user:
                return user
            user = TelegramUser(telegram_id=telegram_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user


class UserSettingsRepository(BaseRepository[UserSettings]):
    def __init__(self) -> None:
        super().__init__(UserSettings)

    async def get_or_create_for_user(self, user_id: int) -> UserSettings:
        async with self._sessionmanager.session() as session:
            res = await session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = res.scalar_one_or_none()
            if settings:
                return settings
            settings = UserSettings(user_id=user_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
            return settings

    async def list_market_subscribers(self, *, base_asset: str, quote_asset: str) -> list[tuple[int, float]]:
        async with self._sessionmanager.session() as session:
            res = await session.execute(
                select(TelegramUser.telegram_id, UserSettings.volatility_threshold)
                .join(UserSettings, UserSettings.user_id == TelegramUser.id)
                .join(UserTrackedAsset, UserTrackedAsset.user_id == TelegramUser.id)
                .where(UserSettings.notifications_enabled.is_(True))
                .where(UserTrackedAsset.enabled.is_(True))
                .where(UserTrackedAsset.base_asset == base_asset)
                .where(UserTrackedAsset.quote_asset == quote_asset)
            )
            return [(int(tid), float(thr)) for tid, thr in res.all()]

    async def list_distinct_notify_telegram_ids_with_tracked_assets(self) -> list[int]:
        async with self._sessionmanager.session() as session:
            res = await session.execute(
                select(TelegramUser.telegram_id)
                .join(UserSettings, UserSettings.user_id == TelegramUser.id)
                .join(UserTrackedAsset, UserTrackedAsset.user_id == TelegramUser.id)
                .where(UserSettings.notifications_enabled.is_(True))
                .where(UserTrackedAsset.enabled.is_(True))
                .distinct()
            )
            return [int(tid) for tid in res.scalars().all()]


class UserTrackedAssetRepository(BaseRepository[UserTrackedAsset]):
    def __init__(self) -> None:
        super().__init__(UserTrackedAsset)

    async def list_enabled_assets(self, user_id: int) -> list[UserTrackedAsset]:
        async with self._sessionmanager.session() as session:
            res = await session.execute(
                select(UserTrackedAsset)
                .where(UserTrackedAsset.user_id == user_id)
                .where(UserTrackedAsset.enabled.is_(True))
                .order_by(UserTrackedAsset.added_at.asc())
            )
            return list(res.scalars().all())

    async def list_distinct_enabled_markets(self) -> list[tuple[str, str]]:
        async with self._sessionmanager.session() as session:
            res = await session.execute(
                select(UserTrackedAsset.base_asset, UserTrackedAsset.quote_asset)
                .where(UserTrackedAsset.enabled.is_(True))
                .distinct()
            )
            return [(str(b), str(q)) for b, q in res.all()]

    async def add_asset(
        self,
        user_id: int,
        base_asset: str,
        quote_asset: str = "USDT",
    ) -> UserTrackedAsset:
        base = base_asset.upper()
        quote = quote_asset.upper()

        async with self._sessionmanager.session() as session:
            stmt = (
                insert(UserTrackedAsset)
                .values(
                    user_id=user_id,
                    base_asset=base,
                    quote_asset=quote,
                    enabled=True,
                )
                .on_conflict_do_update(
                    constraint="uq_user_tracked_asset",
                    set_={"enabled": True},
                )
                .returning(UserTrackedAsset)
            )
            res = await session.execute(stmt)
            await session.commit()
            return res.scalar_one()

    async def remove_asset(self, user_id: int, base_asset: str, quote_asset: str = "USDT") -> int:
        async with self._sessionmanager.session() as session:
            res = await session.execute(
                delete(UserTrackedAsset)
                .where(UserTrackedAsset.user_id == user_id)
                .where(UserTrackedAsset.base_asset == base_asset.upper())
                .where(UserTrackedAsset.quote_asset == quote_asset.upper())
            )
            await session.commit()
            return int(res.rowcount or 0)

