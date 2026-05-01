from __future__ import annotations

from sqlalchemy import delete, insert, select

from project.core.db_session import sessionmanager
from project.models.catalog import CatalogCoin


class CatalogRepository:
    async def replace_all(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        async with sessionmanager.session() as session:
            await session.execute(delete(CatalogCoin))
            await session.execute(insert(CatalogCoin).values(rows))
            await session.commit()
        return len(rows)

    async def list_by_market_cap_rank(self, *, source: str = "coingecko", limit: int = 300) -> list[CatalogCoin]:
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(CatalogCoin)
                .where(CatalogCoin.source == source)
                .order_by(CatalogCoin.market_cap_rank.asc())
                .limit(limit)
            )
            return list(res.scalars().all())

    async def get_first_by_symbol(self, *, source: str, symbol: str) -> CatalogCoin | None:
        sym = symbol.strip().upper()
        async with sessionmanager.session() as session:
            res = await session.execute(
                select(CatalogCoin)
                .where(CatalogCoin.source == source)
                .where(CatalogCoin.symbol == sym)
                .order_by(CatalogCoin.market_cap_rank.asc().nulls_last())
                .limit(1)
            )
            return res.scalar_one_or_none()

