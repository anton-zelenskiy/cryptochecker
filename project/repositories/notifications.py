from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from project.core.db_session import sessionmanager
from project.models.notifications import Notification


class NotificationRepository:
    async def insert_ignore(self, row: dict) -> int:
        async with sessionmanager.session() as session:
            stmt = pg_insert(Notification).values(row)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_notification_dedup")
            res = await session.execute(stmt)
            await session.commit()
            return int(getattr(res, "rowcount", 0) or 0)

    async def get_latest_for_market_since(
        self,
        *,
        source: str,
        base_asset: str,
        quote_asset: str,
        decision: str,
        channel: str,
        since: dt.datetime,
    ) -> Notification | None:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(Notification)
                .where(Notification.source == source)
                .where(Notification.base_asset == base_asset)
                .where(Notification.quote_asset == quote_asset)
                .where(Notification.decision == decision)
                .where(Notification.channel == channel)
                .where(Notification.asof_time_utc >= since)
                .order_by(Notification.asof_time_utc.desc())
                .limit(1)
            )
            return res.scalar_one_or_none()

