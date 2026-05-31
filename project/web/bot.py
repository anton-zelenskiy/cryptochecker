from __future__ import annotations

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, Message

from project.core.config import settings
from project.repositories.indicators import IndicatorSnapshotRepository
from project.repositories.users import (
    TelegramUserRepository,
    UserSettingsRepository,
    UserTrackedAssetRepository,
)
from project.marketdata.api.gemini import SignalSummaryInput, summarize_with_gemini
from project.screener.indicator_format import format_indicator_value


router = Router()

_BOT_COMMAND_SPECS: tuple[tuple[str, str], ...] = (
    ("start", "Register and get started"),
    ("help", "List commands"),
    ("track", "Track a market: /track BTC (BTC/USDT)"),
    ("untrack", "Stop tracking: /untrack BTC"),
    ("list", "Show tracked markets"),
    ("summary", "AI summary: /summary BTC"),
)

# Paste into BotFather: @BotFather → /setcommands → pick bot → send the block below (no leading slashes).
TELEGRAM_BOT_COMMANDS_FOR_SETTINGS = "\n".join(f"{cmd} - {desc}" for cmd, desc in _BOT_COMMAND_SPECS)


def format_bot_help_text() -> str:
    lines = ["<b>Commands</b>"] + [f"/{cmd} - {desc}" for cmd, desc in _BOT_COMMAND_SPECS]
    return "\n".join(lines)


async def setup_telegram_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [BotCommand(command=c, description=d) for c, d in _BOT_COMMAND_SPECS],
    )


def get_bot() -> Bot:
    return Bot(token=settings.TELEGRAM_BOT_TOKEN)


async def send_telegram_text(*, chat_id: int, text: str) -> None:
    bot = get_bot()
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    finally:
        await bot.session.close()


@router.message(Command("start"))
async def start(message: Message) -> None:
    user_repo = TelegramUserRepository()
    settings_repo = UserSettingsRepository()
    user = await user_repo.get_or_create(int(message.from_user.id))
    await settings_repo.get_or_create_for_user(user.id)
    await message.answer(
        "CryptoChecker is running.\n\n" + format_bot_help_text(),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(format_bot_help_text(), parse_mode="HTML")


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
            macd_hist=snap.macd_hist,
            adx_14=snap.adx_14,
        ),
        model="gemini-3.1-flash-lite-preview",
    )

    if ai_text:
        await message.answer(ai_text)
    else:
        await message.answer(
            f"{asset}/USDT: decision={decision}, confidence={confidence:.4f}, "
            f"rsi14={format_indicator_value(snap.rsi_14)} "
            f"macd_hist={format_indicator_value(snap.macd_hist)} "
            f"adx14={format_indicator_value(snap.adx_14)}"
        )


def build_bot() -> tuple[Bot, Dispatcher]:
    bot = get_bot()
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp

