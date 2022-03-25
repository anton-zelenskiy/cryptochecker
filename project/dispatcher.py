import enum
from logging import getLogger
from queue import Queue

import telegram
from pycoingecko import CoinGeckoAPI
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)

from project.core.redis import get_redis
from project import settings

cg = CoinGeckoAPI()
redis = get_redis()

logger = getLogger(__name__)


def init_dispatcher(bot: telegram.Bot) -> Dispatcher:
    queue = Queue()
    dp = Dispatcher(bot=bot, update_queue=queue)
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('eth', eth))
    dp.add_handler(CommandHandler('btc', btc))
    dp.add_handler(CommandHandler('enable_notifications', enable_notifications))
    dp.add_handler(
        CommandHandler('disable_notifications', disable_notifications)
    )

    volatility_handler = ConversationHandler(
        entry_points=[CommandHandler('set_volatility', set_volatility_command)],
        states={
            VolatilityState.SET_VOLATILITY.value: [
                MessageHandler(Filters.text, set_volatility_value)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    dp.add_handler(volatility_handler)

    return dp


def start(update: Update, context: CallbackContext):
    """Starts the conversation and asks the user about their gender."""
    reply_keyboard = [['Boy', 'Girl', 'Other']]

    update.message.reply_text(
        'Hi! My name is Professor Bot. I will hold a conversation with you. '
        'Send /cancel to stop talking to me.\n\n'
        'Are you a boy or a girl?',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
            input_field_placeholder='Boy or Girl?'
        ),
    )


def eth(update: Update, context: CallbackContext) -> None:
    """Starts the conversation and asks the user about their gender."""
    result = cg.get_price(ids=['ethereum'], vs_currencies='usd')
    update.message.reply_text(result)


def btc(update: Update, context: CallbackContext) -> None:
    """Starts the conversation and asks the user about their gender."""
    result = cg.get_price(ids=['bitcoin'], vs_currencies='usd')
    update.message.reply_text(result)


def enable_notifications(update: Update, context: CallbackContext) -> None:
    redis.sadd(settings.CHATS_CACHE_KEY, update.message.chat.id)
    update.message.reply_text('Notifications are successfully enabled')


def disable_notifications(update: Update, context: CallbackContext) -> None:
    redis.srem(settings.CHATS_CACHE_KEY, update.message.chat.id)
    update.message.reply_text('Notifications are successfully disabled')


class VolatilityState(enum.Enum):
    SET_VOLATILITY = 'SET'


def set_volatility_command(update: Update, context: CallbackContext) -> str:
    update.message.reply_text('Please set volatility threshold:')

    return VolatilityState.SET_VOLATILITY.value


def set_volatility_value(update: Update, context: CallbackContext) -> None:
    try:
        value = float(update.message.text)
    except ValueError as e:
        logger.error(e)
        update.message.reply_text('invalid value, try again:')
        return VolatilityState.SET_VOLATILITY.value

    redis.set(f'volatility:user:{update.message.chat.id}:threshold', value)
    update.message.reply_text('Volatility threshold updated successfully')

    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext) -> int:
    """Cancels and ends the conversation."""
    update.message.reply_text(
        'cancel',
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END
