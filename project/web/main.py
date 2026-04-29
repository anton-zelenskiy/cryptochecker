from __future__ import annotations

import contextlib

import structlog
import json
import urllib.parse

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Query
from sqlalchemy import select

from project.core.config import settings
from project.services.catalog import refresh_catalog_top300_non_stablecoins
from project.web.telegram_webapp import verify_telegram_init_data
from project.repositories.users import TelegramUserRepository, UserTrackedAssetRepository
from project.models import candles as _candles  # noqa: F401
from project.models import catalog as _catalog  # noqa: F401
from project.models import indicators as _indicators  # noqa: F401
from project.models import paper_trading as _paper  # noqa: F401
from project.models import users as _users  # noqa: F401
from project.web.bot import build_bot


logger = structlog.get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    with contextlib.suppress(Exception):
        await refresh_catalog_top300_non_stablecoins()

    bot, dp = app.state.bot, app.state.dp

    # webhook_url = f"{settings.TELEGRAM_WEBHOOK_BASE_URL.rstrip('/')}{settings.TELEGRAM_WEBHOOK_PATH}"
    # await bot.set_webhook(
    #     url=webhook_url,
    #     secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
    #     drop_pending_updates=True,
    # )
    # logger.info("webhook set", url=webhook_url)

    yield

    with contextlib.suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=False)
    await bot.session.close()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

bot, dp = build_bot()
app.state.bot = bot
app.state.dp = dp


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(settings.TELEGRAM_WEBHOOK_PATH)
async def telegram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    tg_update = Update.model_validate(update)
    await dp.feed_update(bot, tg_update)
    return {"ok": True}


@app.get("/api/catalog")
async def api_catalog(init_data: str = Query("", alias="initData")) -> list[dict]:
    if init_data and not verify_telegram_init_data(init_data, settings.TELEGRAM_BOT_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid initData")

    from project.models.catalog import CatalogCoin

    from project.core.db_session import sessionmanager
    async with sessionmanager.session() as session:
        res = await session.execute(
            select(CatalogCoin).order_by(CatalogCoin.market_cap_rank.asc()).limit(300)
        )
        coins = list(res.scalars().all())
    return [
        {
            "id": c.coingecko_id,
            "symbol": c.symbol,
            "name": c.name,
            "rank": c.market_cap_rank,
        }
        for c in coins
        if not c.is_stablecoin
    ]


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


@app.get("/api/tracked")
async def api_tracked(init_data: str = Query("", alias="initData")) -> list[dict]:
    if not verify_telegram_init_data(init_data, settings.TELEGRAM_BOT_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid initData")

    telegram_id = _telegram_user_id_from_init_data(init_data)
    user_repo = TelegramUserRepository()
    tracked_repo = UserTrackedAssetRepository()
    user = await user_repo.get_or_create(telegram_id)
    assets = await tracked_repo.list_enabled_assets(user.id)
    return [{"base": a.base_asset, "quote": a.quote_asset, "enabled": a.enabled} for a in assets]

