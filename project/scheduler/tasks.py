from typing import Iterable, Set

from project import settings
from project.api.coingecko import get_currency_code_id_map, get_currency_prices
from project.core.redis import get_redis
from project.currencies.structures import Ratio
from project.currencies.volatility import get_volatility_data
from project.utils import get_currency_prices_display

default_currency_codes = {'BTC', 'ETH'}


def send_currency_prices():
    """Notify subscribers about currency prices every hour."""
    from project.app import tg_bot

    redis = get_redis()
    chat_ids = redis.smembers(settings.CHATS_CACHE_KEY)

    if not chat_ids:
        return

    currency_code_map = get_currency_code_id_map()
    all_user_currencies = get_all_user_currencies(chat_ids)

    user_currency_codes = set()
    for curr in all_user_currencies.values():
        user_currency_codes.update(set(curr))

    all_currency_codes = default_currency_codes | user_currency_codes

    currency_ids = [
        currency_code_map.get(code)
        for code in all_currency_codes
    ]

    currency_prices = get_currency_prices(currency_ids)

    for chat_id in chat_ids:
        user_currencies = all_user_currencies.get(chat_id, [])
        user_currency_prices = [
            item for item in currency_prices
            if item.currency_code in default_currency_codes | user_currencies
        ]
        prices_data = {
            item.currency_code: item.price
            for item in user_currency_prices
        }

        tg_bot.send_message(
            chat_id=int(chat_id),
            text=get_currency_prices_display(prices_data),
            parse_mode='HTML',
        )

    return currency_prices


def check_volatility():
    """Notify subscribers about currency volatility."""
    from project.app import tg_bot

    redis = get_redis()
    chat_ids = redis.smembers(settings.CHATS_CACHE_KEY)

    if not chat_ids:
        return

    all_user_currencies = get_all_user_currencies(chat_ids)

    user_currency_codes = set()
    for curr in all_user_currencies.values():
        user_currency_codes.update(set(curr))

    all_currency_codes = default_currency_codes | user_currency_codes

    volatility_data_by_currency = get_volatility_data_for_currencies(
        all_currency_codes
    )

    for chat_id in chat_ids:
        user_currencies = all_user_currencies.get(chat_id, set())
        volatility_threshold = get_volatility_threshold(chat_id)

        for currency in default_currency_codes | user_currencies:
            volatility = volatility_data_by_currency.get(currency)

            if not volatility:
                continue

            for period_min, volatility_data in volatility.items():
                if volatility_data.volatility > volatility_threshold:
                    ratio = Ratio.get_ratio_display(volatility_data.ratio)
                    message = (
                        f'Price alert for {currency}. Period (min): {period_min}, '
                        f'volatility: {volatility_data.volatility} % ({ratio}), '
                        f'latest price: {volatility_data.x2}, '
                        f'old price: {volatility_data.x1}'
                    )
                    tg_bot.send_message(
                        chat_id=int(chat_id),
                        text=message,
                        parse_mode='HTML',
                    )


def get_all_user_currencies(chat_ids: Iterable[str]):
    result = {}
    for chat_id in chat_ids:
        result.update({
            chat_id: get_user_currencies(chat_id)
        })
    return result


def get_user_currencies(chat_id: str):
    redis = get_redis()

    return redis.smembers(
        f'volatility:user:{chat_id}:currencies'
    ) or set()


def get_volatility_threshold(chat_id):
    redis = get_redis()

    try:
        volatility_threshold = float(
            redis.get(f'volatility:user:{chat_id}:threshold')
        )
    except TypeError:
        volatility_threshold = settings.VOLATILITY_THRESHOLD_PERCENT

    return volatility_threshold


def get_volatility_data_for_currencies(currency_codes: Set[str]):
    result = {}

    currency_code_map = get_currency_code_id_map()

    for currency_code in currency_codes:
        currency_id = currency_code_map.get(currency_code)
        if not currency_id:
            continue

        result.update({
            currency_code: get_volatility_data(
                currency_id=currency_id
            )
        })

    return result
