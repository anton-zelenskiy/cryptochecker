from __future__ import annotations
import structlog
from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Query
from starlette.requests import Request

from project.core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter()

ADMIN_TOKEN_HEADER = "x-cryptochecker-admin-token"


@router.post(settings.TELEGRAM_WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    bot, dp = request.app.state.bot, request.app.state.dp
    tg_update = Update.model_validate(update)
    await dp.feed_update(bot, tg_update)
    return {"ok": True}


def _require_admin_token(x_cryptochecker_admin_token: str | None) -> None:
    if not x_cryptochecker_admin_token or x_cryptochecker_admin_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.get(settings.TELEGRAM_WEBHOOK_PATH)
async def telegram_webhook_info(
    request: Request,
    x_cryptochecker_admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
) -> dict:
    # _require_admin_token(x_cryptochecker_admin_token)
    bot = request.app.state.bot
    info = await bot.get_webhook_info()
    return info.model_dump()


@router.get(f"{settings.TELEGRAM_WEBHOOK_PATH}/set")
async def telegram_webhook_set(
    request: Request,
    x_cryptochecker_admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
    url: str | None = Query(default=None),
    drop_pending_updates: bool = Query(default=True),
) -> dict[str, str | bool]:
    # _require_admin_token(x_cryptochecker_admin_token)
    bot = request.app.state.bot

    logger.info("setting telegram webhook", url=settings.TELEGRAM_WEBHOOK_URL)

    await bot.set_webhook(
        url=settings.TELEGRAM_WEBHOOK_URL,
        secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
        drop_pending_updates=drop_pending_updates,
    )
    return {"ok": True, "url": settings.TELEGRAM_WEBHOOK_URL}


@router.delete(settings.TELEGRAM_WEBHOOK_PATH)
async def telegram_webhook_delete(
    request: Request,
    x_cryptochecker_admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
    drop_pending_updates: bool = Query(default=False),
) -> dict[str, bool]:
    # _require_admin_token(x_cryptochecker_admin_token)
    bot = request.app.state.bot
    await bot.delete_webhook(drop_pending_updates=drop_pending_updates)
    return {"ok": True}
