import enum
from queue import Queue

import structlog
from scheduler.check_volatility import (
    default_currency_codes,
)
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import PARSEMODE_HTML
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Dispatcher,
    Filters,
    MessageHandler,
)

from project import constants
from project.api.kucoin import KucoinMarketAPI
from project.core.redis import SettingStorage
from project.currencies.structures import AppMode, Coin
from project.utils import error_handler, rpm_counter

setting_storage = SettingStorage()

market_api = KucoinMarketAPI()

logger = structlog.get_logger(__name__)


class CurrencyState(enum.IntEnum):
    ADD_CURRENCY = 1
    DEL_CURRENCY = 2


class SettingState(enum.IntEnum):
    CHOOSE_SETTING = 1
    HANDLE_SET_APP_MODE = 2
    HANDLE_SET_VOLATILITY_THRESHOLD = 3
    HANDLE_TOGGLE_NOTIFICATIONS = 4


class SettingEnum(enum.Enum):
    CMD_SHOW_CURRENT_SETTINGS = 'CMD_SHOW_CURRENT_SETTINGS'
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
    cancel - Cancel conversation
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
                CallbackQueryHandler(
                    handle_show_current_settings,
                    pattern=f'^{SettingEnum.CMD_SHOW_CURRENT_SETTINGS.value}$'
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


@error_handler
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        'Hi! Type currency code to get its price',
    )


@error_handler
def handle_settings(update: Update, context: CallbackContext) -> int:
    buttons = [
        [
            InlineKeyboardButton(
                text='show current settings',
                callback_data=SettingEnum.CMD_SHOW_CURRENT_SETTINGS.value,
            )
        ],
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


@error_handler
def handle_show_current_settings(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id

    notifications_is_enabled = setting_storage.is_notifications_enabled(user_id)
    volatility_threshold = setting_storage.get_volatility_threshold(user_id)
    app_mode = setting_storage.get_app_mode(user_id)
    rpm_stats = rpm_counter.stats()

    query.edit_message_text(
        f"Notifications: <b>{'enabled' if notifications_is_enabled else 'disabled'}</b>\n"
        f"Volatility threshold: <b>{volatility_threshold}%</b>\n"
        f"App mode: <b>{app_mode.name}</b>\n"
        f"RPM: <b>top - {str(rpm_stats['top'])}; avg: {rpm_stats['avg']}</b>",
        parse_mode=PARSEMODE_HTML,
    )

    return ConversationHandler.END


@error_handler
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


@error_handler
def handle_check_selected_coins(
    update: Update,
    context: CallbackContext
) -> int:
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id

    setting_storage.set_app_mode(chat_id=user_id, value=AppMode.CHECK_SELECTED_COINS)

    query.edit_message_text(text=f'Success! current app mode: {AppMode.CHECK_SELECTED_COINS.name}')

    return ConversationHandler.END


@error_handler
def handle_check_all_coins(
    update: Update,
    context: CallbackContext
) -> int:
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id

    setting_storage.set_app_mode(chat_id=user_id, value=AppMode.CHECK_ALL_COINS)

    query.edit_message_text(text=f'Success! current app mode: {AppMode.CHECK_ALL_COINS.name}')

    return ConversationHandler.END


@error_handler
def handle_set_volatility_threshold_command(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    query.edit_message_text('Please set volatility threshold:')

    return SettingState.HANDLE_SET_VOLATILITY_THRESHOLD


@error_handler
def handle_set_volatility_threshold_value(update: Update, context: CallbackContext) -> int:
    try:
        value = float(update.message.text)
    except ValueError as e:
        logger.error(e)
        update.message.reply_text('invalid value, try again:')
        return SettingState.HANDLE_SET_VOLATILITY_THRESHOLD

    user_id = update.message.from_user.id
    setting_storage.set_volatility_threshold(user_id, value)

    update.message.reply_text('Volatility threshold updated successfully')

    return ConversationHandler.END


@error_handler
def handle_toggle_notifications(update: Update, context: CallbackContext) -> int:
    logger.info('toggle notif')
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id

    is_enabled = setting_storage.toggle_notifications(user_id)

    query.edit_message_text(
        'Notifications have been enabled' if is_enabled else 'Notifications have been disabled'
    )

    return ConversationHandler.END


@error_handler
def list_currencies(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id

    user_currencies = setting_storage.get_user_currencies(user_id)
    user_currencies = list(user_currencies)

    chunks = [
        user_currencies[x:x + 5]
        for x in range(0, len(user_currencies), 5)
    ]

    update.message.reply_text(
        'Selected coins:',
        reply_markup=ReplyKeyboardMarkup(
            chunks,
            one_time_keyboard=True,
        )
    )

    return ConversationHandler.END


@error_handler
def add_currency_command(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Please type currency code:')

    return CurrencyState.ADD_CURRENCY


@error_handler
def add_currency_value(update: Update, context: CallbackContext) -> int:
    currency_codes = str(update.message.text).lower().strip().replace(' ', '').split(',')
    for currency_code in currency_codes:
        if not market_api.is_currency_code_exists(currency_code):
            update.message.reply_text(f'invalid currency: {currency_code}, try again:')
            return CurrencyState.ADD_CURRENCY

        user_id = update.message.from_user.id

        setting_storage.watch_coin(user_id, currency_code)
    update.message.reply_text('Currency added successfully')

    return ConversationHandler.END

@error_handler
def del_currency_command(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Please type currency code to delete:')

    return CurrencyState.DEL_CURRENCY


@error_handler
def del_currency_value(update: Update, context: CallbackContext) -> int:
    currency_code = str(update.message.text).lower()

    if not market_api.is_currency_code_exists(currency_code):
        update.message.reply_text('invalid currency, try again:')
        return CurrencyState.DEL_CURRENCY.value

    user_id = update.message.from_user.id

    setting_storage.unwatch_coin(user_id, currency_code)
    update.message.reply_text('Currency deleted successfully')

    return ConversationHandler.END


@error_handler
def cancel(update: Update, context: CallbackContext) -> int:
    """Cancels and ends the conversation."""
    update.message.reply_text(
        'cancel',
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


@error_handler
def currency_price(update: Update, context: CallbackContext) -> None:
    currency_code = str(update.message.text).lower()

    if not market_api.is_currency_code_exists(currency_code):
        update.message.reply_text('unknown command')

    coin_prices = market_api.get_market_data(currency_codes=[currency_code])

    update.message.reply_text(
        Coin.display(coin_prices, constants.DEFAULT_VOLATILITY_THRESHOLD_PERCENT),
        parse_mode=PARSEMODE_HTML
    )


@error_handler
def info(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    user_currencies = setting_storage.get_user_currencies(user_id)
    currency_codes = default_currency_codes | user_currencies

    coin_prices = market_api.get_market_data(currency_codes=currency_codes)

    update.message.reply_text(
        Coin.display(coin_prices, constants.DEFAULT_VOLATILITY_THRESHOLD_PERCENT),
        parse_mode=PARSEMODE_HTML
    )
