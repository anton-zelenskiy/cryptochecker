from __future__ import annotations

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from project.core.config import settings
from project.repositories.indicators import IndicatorSnapshotRepository
from project.repositories.users import (
    TelegramUserRepository,
    UserSettingsRepository,
    UserTrackedAssetRepository,
)
from project.services.gemini import SignalSummaryInput, summarize_with_gemini


router = Router()


@router.message(Command("start"))
async def start(message: Message) -> None:
    user_repo = TelegramUserRepository()
    settings_repo = UserSettingsRepository()
    user = await user_repo.get_or_create(int(message.from_user.id))
    await settings_repo.get_or_create_for_user(user.id)
    await message.answer("CryptoChecker bot is running. Use /track BTC to track.")


@router.message(Command("track"))
async def track(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Usage: /track BTC")
        return
    asset = parts[1].upper()

    user_repo = TelegramUserRepository()
    tracked_repo = UserTrackedAssetRepository()
    user = await user_repo.get_or_create(int(message.from_user.id))
    await tracked_repo.add_asset(user.id, asset)
    await message.answer(f"Tracking enabled for {asset}/USDT")


@router.message(Command("untrack"))
async def untrack(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Usage: /untrack BTC")
        return
    asset = parts[1].upper()

    user_repo = TelegramUserRepository()
    tracked_repo = UserTrackedAssetRepository()
    user = await user_repo.get_or_create(int(message.from_user.id))
    removed = await tracked_repo.remove_asset(user.id, asset)
    await message.answer(f"Removed: {removed}")


@router.message(Command("list"))
async def list_assets(message: Message) -> None:
    user_repo = TelegramUserRepository()
    tracked_repo = UserTrackedAssetRepository()
    user = await user_repo.get_or_create(int(message.from_user.id))
    assets = await tracked_repo.list_enabled_assets(user.id)
    if not assets:
        await message.answer("No tracked assets. Use /track BTC")
        return
    text = "Tracked:\n" + "\n".join(f"- {a.base_asset}/{a.quote_asset}" for a in assets)
    await message.answer(text)


@router.message(Command("summary"))
async def summary(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Usage: /summary BTC")
        return
    asset = parts[1].upper()

    repo = IndicatorSnapshotRepository()
    snap = await repo.get_latest(source="kucoin", base_asset=asset, quote_asset="USDT", timeframe="5m")
    if not snap:
        await message.answer("No indicator data yet. Wait for Celery tick.")
        return

    decision = "WAIT"
    confidence = 0.0
    if snap.rsi_14 is not None:
        if snap.rsi_14 <= 30:
            decision = "LONG"
            confidence = min(1.0, (30 - snap.rsi_14) / 30 + 0.5)
        elif snap.rsi_14 >= 70:
            decision = "SHORT"
            confidence = min(1.0, (snap.rsi_14 - 70) / 30 + 0.5)

    ai_text = await summarize_with_gemini(
        SignalSummaryInput(
            symbol=f"{asset}/USDT",
            decision=decision,
            confidence=confidence,
            rsi_14=snap.rsi_14,
        )
    )

    if ai_text:
        await message.answer(ai_text)
    else:
        await message.answer(f"{asset}/USDT: decision={decision}, confidence={confidence:.2f}, rsi14={snap.rsi_14}")


def build_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp

