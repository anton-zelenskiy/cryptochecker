from __future__ import annotations

import json
import urllib.parse

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from project.core.config import settings
from project.repositories.users import TelegramUserRepository, UserTrackedAssetRepository
from project.web.telegram_webapp import verify_telegram_init_data

router = APIRouter()


@router.get("/api/catalog")
async def api_catalog(init_data: str = Query("", alias="initData")) -> list[dict]:
    if init_data and not verify_telegram_init_data(init_data, settings.TELEGRAM_BOT_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid initData")

    from project.core.db_session import sessionmanager
    from project.models.catalog import CatalogCoin

    async with sessionmanager.session() as session:
        res = await session.execute(
            select(CatalogCoin).order_by(CatalogCoin.market_cap_rank.asc()).limit(300)
        )
        coins = list(res.scalars().all())

    return [
        {
            "id": c.coingecko_id,
            "source": c.source,
            "symbol": c.symbol,
            "name": c.name,
            "rank": c.market_cap_rank,
        }
        for c in coins
        if not c.is_stablecoin
    ]


@router.get("/api/tracked")
async def api_tracked(init_data: str = Query("", alias="initData")) -> list[dict]:
    if not verify_telegram_init_data(init_data, settings.TELEGRAM_BOT_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid initData")

    telegram_id = _telegram_user_id_from_init_data(init_data)
    user_repo = TelegramUserRepository()
    tracked_repo = UserTrackedAssetRepository()
    user = await user_repo.get_or_create(telegram_id)
    assets = await tracked_repo.list_enabled_assets(user.id)
    return [{"base": a.base_asset, "quote": a.quote_asset, "enabled": a.enabled} for a in assets]


def _telegram_user_id_from_init_data(init_data: str) -> int:
    params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    user_json = params.get("user")
    if not user_json:
        raise HTTPException(status_code=400, detail="initData missing user")
    try:
        user = json.loads(user_json)
        return int(user["id"])
    except Exception:
        raise HTTPException(status_code=400, detail="invalid initData user")

