import enum
from logging import getLogger
from queue import Queue

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, Bot
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)

from project import settings
from project.api.coingecko import (
    is_currency_code_exists,
    get_currency_prices,
    get_currency_code_id_map,
)
from project.core.redis import get_redis
from project.utils import get_currency_prices_display

redis = get_redis()

logger = getLogger(__name__)


def init_dispatcher(bot: Bot) -> Dispatcher:
    queue = Queue()
    dp = Dispatcher(bot=bot, update_queue=queue)
    dp.add_handler(CommandHandler('start', start))
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

    dp.add_handler(CommandHandler('list_currencies', list_currencies))
    add_currency_handler = ConversationHandler(
        entry_points=[CommandHandler('add_currency', add_currency_command)],
        states={
            CurrencyState.ADD_CURRENCY.value: [
                MessageHandler(Filters.text, add_currency_value)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    dp.add_handler(add_currency_handler)

    dp.add_handler(MessageHandler(Filters.all, currency_price))

    return dp


def start(update: Update, context: CallbackContext):
    reply_keyboard = [
        ['btc', 'eth', 'ada'],
        ['doge', 'xrp', 'link'],
    ]

    update.message.reply_text(
        'Hi! You can check currency price:',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
        ),
    )


def enable_notifications(update: Update, context: CallbackContext) -> None:
    redis.sadd(settings.CHATS_CACHE_KEY, update.message.chat.id)
    update.message.reply_text('Notifications are successfully enabled')


def disable_notifications(update: Update, context: CallbackContext) -> None:
    redis.srem(settings.CHATS_CACHE_KEY, update.message.chat.id)
    update.message.reply_text('Notifications are successfully disabled')


class VolatilityState(enum.Enum):
    SET_VOLATILITY = 'SET'


class CurrencyState(enum.Enum):
    ADD_CURRENCY = 'ADD_CURRENCY'
    DEL_CURRENCY = 'DEL_CURRENCY'


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


def list_currencies(update: Update, context: CallbackContext) -> None:
    def get_display_data(data):
        """Wraps info in html tags."""
        rows = []
        for item in data:
            rows.append(f'<b>{item}$</b>')

        return '\n'.join(rows)

    user_currencies = redis.smembers(
        f'volatility:user:{update.message.chat.id}:currencies'
    )

    update.message.reply_text(
        get_display_data(user_currencies),
        parse_mode='HTML'
    )

    return ConversationHandler.END


def add_currency_command(update: Update, context: CallbackContext) -> str:
    update.message.reply_text('Please type currency code:')

    return CurrencyState.ADD_CURRENCY.value


def add_currency_value(update: Update, context: CallbackContext) -> None:
    currency_code = str(update.message.text).upper()

    if not is_currency_code_exists(currency_code):
        update.message.reply_text('invalid currency, try again:')
        return CurrencyState.ADD_CURRENCY.value

    redis.sadd(
        f'volatility:user:{update.message.chat.id}:currencies',
        currency_code
    )
    update.message.reply_text('Currency added successfully')

    return ConversationHandler.END


def del_currency_command(update: Update, context: CallbackContext) -> str:
    update.message.reply_text('Please type currency code to delete:')

    return CurrencyState.DEL_CURRENCY.value


def del_currency_value(update: Update, context: CallbackContext) -> None:
    currency_code = str(update.message.text).upper()

    if not is_currency_code_exists(currency_code):
        update.message.reply_text('invalid currency, try again:')
        return CurrencyState.DEL_CURRENCY.value

    redis.srem(
        f'volatility:user:{update.message.chat.id}:currencies',
        currency_code
    )
    update.message.reply_text('Currency deleted successfully')

    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext) -> int:
    """Cancels and ends the conversation."""
    update.message.reply_text(
        'cancel',
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


def currency_price(update: Update, context: CallbackContext) -> None:
    currency_code = update.message.text

    currency_id = get_currency_code_id_map().get(currency_code)
    if not currency_id:
        update.message.reply_text('unknown command')

    currency_prices = get_currency_prices(currency_ids=[currency_id])
    prices_data = {
        item.currency_code: item.price
        for item in currency_prices
    }

    update.message.reply_text(
        get_currency_prices_display(prices_data),
        parse_mode='HTML'
    )
