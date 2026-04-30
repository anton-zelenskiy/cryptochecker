from __future__ import annotations

import datetime as dt

from sqlalchemy.dialects.postgresql import insert

from project.core.db_session import sessionmanager
from project.models.coin_metadata import CoinMetadata


class CoinMetadataRepository:
    async def upsert_platforms(
        self,
        *,
        coin_id: str,
        platforms: dict,
        fetched_at: dt.datetime,
        source: str = "coingecko",
    ) -> None:
        row = {
            "source": source,
            "coin_id": coin_id,
            "platforms": platforms,
            "fetched_at": fetched_at,
        }
        async with sessionmanager.session() as session:
            stmt = insert(CoinMetadata).values([row])
            stmt = stmt.on_conflict_do_update(
                constraint="uq_coin_metadata_identity",
                set_={
                    "platforms": stmt.excluded.platforms,
                    "fetched_at": stmt.excluded.fetched_at,
                    "updated_at": dt.datetime.now(dt.timezone.utc),
                },
            )
            await session.execute(stmt)
            await session.commit()

