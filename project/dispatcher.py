import enum
from logging import getLogger
from queue import Queue

from scheduler.check_volatility import (
    default_currency_codes,
)
from project.core.redis import get_user_currencies
from telegram import Bot, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Dispatcher,
    Filters,
    MessageHandler,
)

from project import settings
from project import constants
from project.currencies.structures import Coin
from project.api.coingecko import (
    get_currency_prices,
    is_currency_code_exists,
)
from project.core.redis import get_redis, SettingStorage
from project.currencies.structures import AppMode

redis = get_redis()

setting_storage = SettingStorage()

logger = getLogger(__name__)


class CurrencyState(enum.IntEnum):
    ADD_CURRENCY = 1
    DEL_CURRENCY = 2


class SettingState(enum.IntEnum):
    CHOOSE_SETTING = 1
    HANDLE_SET_APP_MODE = 2
    HANDLE_SET_VOLATILITY_THRESHOLD = 3
    HANDLE_TOGGLE_NOTIFICATIONS = 4


class SettingEnum(enum.Enum):
    CMD_SET_APP_MODE = 'CMD_SET_APP_MODE'
    CMD_CHECK_SELECTED_COINS = 'CMD_CHECK_SELECTED_COINS'
    CMD_CHECK_ALL_COINS = 'CMD_CHECK_ALL_COINS'

    CMD_SET_VOLATILITY_THRESHOLD = 'CMD_SET_VOLATILITY_THRESHOLD'

    CMD_TOGGLE_NOTIFICATIONS = 'CMD_TOGGLE_NOTIFICATIONS'


def init_dispatcher(bot: Bot) -> Dispatcher:
    """
    start - Start bot
    info - Get price of the list of cryptocurrencies
    settings - Set app settings
    list_currencies - List of currencies used by volatility checker
    add_currency - Add currency to volatility checker
    del_currency - Delete currency from volatility checker
    """
    queue = Queue()
    dp = Dispatcher(bot=bot, update_queue=queue)
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('info', info))

    settings_handler = ConversationHandler(
        entry_points=[CommandHandler('settings', handle_settings)],
        states={
            SettingState.CHOOSE_SETTING: [
                CallbackQueryHandler(
                    handle_set_app_mode_command,
                    pattern=f'^{SettingEnum.CMD_SET_APP_MODE.value}$'
                ),
                CallbackQueryHandler(
                    handle_set_volatility_threshold_command,
                    pattern=f'^{SettingEnum.CMD_SET_VOLATILITY_THRESHOLD.value}$'
                ),
                CallbackQueryHandler(
                    handle_toggle_notifications,
                    pattern=f'^{SettingEnum.CMD_TOGGLE_NOTIFICATIONS.value}$'
                ),
            ],
            SettingState.HANDLE_SET_APP_MODE: [
                CallbackQueryHandler(
                    handle_check_selected_coins,
                    pattern=SettingEnum.CMD_CHECK_SELECTED_COINS.value
                ),
                CallbackQueryHandler(
                    handle_check_all_coins,
                    pattern=SettingEnum.CMD_CHECK_ALL_COINS.value
                ),
            ],
            SettingState.HANDLE_SET_VOLATILITY_THRESHOLD: [
                MessageHandler(Filters.text, handle_set_volatility_threshold_value)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    dp.add_handler(settings_handler)

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

    del_currency_handler = ConversationHandler(
        entry_points=[CommandHandler('del_currency', del_currency_command)],
        states={
            CurrencyState.DEL_CURRENCY.value: [
                MessageHandler(Filters.text, del_currency_value)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    dp.add_handler(del_currency_handler)

    dp.add_handler(MessageHandler(Filters.all, currency_price))

    return dp


def start(update: Update, context: CallbackContext):
    reply_keyboard = [
        ['btc', 'eth', 'ada'],
        ['doge', 'xrp', 'link'],
    ]

    update.message.reply_text(
        'Hi! Type currency code to get price',
        # reply_markup=ReplyKeyboardMarkup(
        #     reply_keyboard,
        #     one_time_keyboard=True,
        # ),
    )


def handle_settings(update: Update, context: CallbackContext) -> int:
    buttons = [
        [
            InlineKeyboardButton(
                text='set app mode',
                callback_data=SettingEnum.CMD_SET_APP_MODE.value,
            )
        ],
        [
            InlineKeyboardButton(
                text='set volatility threshold',
                callback_data=SettingEnum.CMD_SET_VOLATILITY_THRESHOLD.value,
            )
        ],
        [
            InlineKeyboardButton(
                text='toggle notifications',
                callback_data=SettingEnum.CMD_TOGGLE_NOTIFICATIONS.value,
            )
        ],
    ]

    update.message.reply_text(
        text='Edit settings:',
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    return SettingState.CHOOSE_SETTING


def handle_set_app_mode_command(
    update: Update,
    context: CallbackContext
) -> int:
    query = update.callback_query
    query.answer()

    buttons = [
        [
            InlineKeyboardButton(
                text='check selected coins',
                callback_data=SettingEnum.CMD_CHECK_SELECTED_COINS.value,
            )
        ],
        [
            InlineKeyboardButton(
                text='check all coins',
                callback_data=SettingEnum.CMD_CHECK_ALL_COINS.value,
            )
        ],
    ]

    query.edit_message_text(
        text='Please set app mode:',
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    return SettingState.HANDLE_SET_APP_MODE


def handle_check_selected_coins(
    update: Update,
    context: CallbackContext
) -> int:
    query = update.callback_query
    query.answer()

    chat_id = update.message.chat.id

    setting_storage.set_app_mode(chat_id=chat_id, value=AppMode.CHECK_SELECTED_COINS)

    query.edit_message_text(text=f'Success! current app mode: {AppMode.CHECK_SELECTED_COINS.name}')

    return ConversationHandler.END


def handle_check_all_coins(
    update: Update,
    context: CallbackContext
) -> int:
    query = update.callback_query
    query.answer()

    chat_id = update.message.chat.id

    setting_storage.set_app_mode(chat_id=chat_id, value=AppMode.CHECK_ALL_COINS)

    query.edit_message_text(text=f'Success! current app mode: {AppMode.CHECK_ALL_COINS.name}')

    return ConversationHandler.END


def handle_set_volatility_threshold_command(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    query.edit_message_text('Please set volatility threshold:')

    return SettingState.HANDLE_SET_VOLATILITY_THRESHOLD


def handle_set_volatility_threshold_value(update: Update, context: CallbackContext) -> int:
    try:
        value = float(update.message.text)
    except ValueError as e:
        logger.error(e)
        update.message.reply_text('invalid value, try again:')
        return SettingState.HANDLE_SET_VOLATILITY_THRESHOLD

    redis.set(f'volatility:user:{update.message.chat.id}:threshold', value)

    update.message.reply_text('Volatility threshold updated successfully')

    return ConversationHandler.END


def handle_toggle_notifications(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    # chat_id = update.message.chat.id
#
    # is_enabled = setting_storage.toggle_notifications(chat_id)

    query.edit_message_text(
        'Notifications have been enabled' # if is_enabled else 'Notifications have been disabled'
    )

    return ConversationHandler.END


def list_currencies(update: Update, context: CallbackContext) -> int:
    def get_display_data(data):
        """Wraps info in html tags."""
        rows = []
        for item in data:
            rows.append(f'<b>{item}</b>')

        return '\n'.join(rows)

    user_currencies = redis.smembers(
        f'volatility:user:{update.message.chat.id}:currencies'
    )

    update.message.reply_text(
        get_display_data(user_currencies),
        parse_mode='HTML'
    )

    return ConversationHandler.END


def add_currency_command(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Please type currency code:')

    return CurrencyState.ADD_CURRENCY


def add_currency_value(update: Update, context: CallbackContext) -> int:
    currency_code = str(update.message.text).lower()

    if not is_currency_code_exists(currency_code):
        update.message.reply_text('invalid currency, try again:')
        return CurrencyState.ADD_CURRENCY

    redis.sadd(
        f'volatility:user:{update.message.chat.id}:currencies',
        currency_code
    )
    update.message.reply_text('Currency added successfully')

    return ConversationHandler.END


def del_currency_command(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Please type currency code to delete:')

    return CurrencyState.DEL_CURRENCY


def del_currency_value(update: Update, context: CallbackContext) -> int:
    currency_code = str(update.message.text).lower()

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
    currency_code = str(update.message.text).lower()

    if not is_currency_code_exists(currency_code):
        update.message.reply_text('unknown command')

    coin_prices = get_currency_prices(currency_codes=[currency_code])

    update.message.reply_text(
        Coin.display(coin_prices, constants.DEFAULT_VOLATILITY_THRESHOLD_PERCENT),
        parse_mode='HTML'
    )


def info(update: Update, context: CallbackContext) -> None:
    user_currencies = get_user_currencies(update.message.chat.id)
    currency_codes = default_currency_codes | user_currencies

    coin_prices = get_currency_prices(currency_codes=currency_codes)

    update.message.reply_text(
        Coin.display(coin_prices, constants.DEFAULT_VOLATILITY_THRESHOLD_PERCENT),
        parse_mode='HTML'
    )
