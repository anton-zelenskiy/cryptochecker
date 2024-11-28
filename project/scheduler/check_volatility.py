import itertools
import logging
from typing import Iterable, Set

from project import settings
from project.api.coingecko import (
    get_currency_code_id_map,
    get_currency_prices,
    get_ohlc,
    get_daily_currency_history,
    STEP_MINUTES
)
from project.core.redis import get_redis
from project.currencies.structures import ICON_ALERT, Ratio, VolatilityValue

from project.utils import get_currency_prices_display

logger = logging.getLogger(__name__)

BORDER_PERCENTAGE = 2
default_currency_codes = {'btc', 'eth'}


def send_currency_prices():
    """Notify subscribers about currency prices every hour."""
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

    currency_prices = get_currency_prices(currency_codes=all_currency_codes)

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


def check_volatility(minutes: int):
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
        currency_codes=all_currency_codes,
        minutes=minutes
    )

    for chat_id in chat_ids:
        user_currencies = all_user_currencies.get(chat_id, set())
        volatility_threshold = get_volatility_threshold(chat_id)

        for currency in default_currency_codes | user_currencies:
            volatility = volatility_data_by_currency.get(currency)

            if not volatility:
                continue

            if volatility.volatility > volatility_threshold:
                ratio = Ratio.get_ratio_display(volatility.ratio)

                lower_price = volatility.calculate_lower_value(volatility.x2, BORDER_PERCENTAGE)
                upper_price = volatility.calculate_upper_value(volatility.x2, BORDER_PERCENTAGE)

                message = (
                    f'{ICON_ALERT} {currency}: {minutes} min., {volatility.volatility}% ({ratio}), '
                    f'price: {volatility.x2} ({lower_price} - {upper_price}). '
                    f'old price: {volatility.x1}'
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

    currencies = redis.smembers(
        f'volatility:user:{chat_id}:currencies'
    ) or set()

    return {i.lower() for i in currencies}


def get_volatility_threshold(chat_id):
    redis = get_redis()

    try:
        volatility_threshold = float(
            redis.get(f'volatility:user:{chat_id}:threshold')
        )
    except TypeError:
        volatility_threshold = settings.VOLATILITY_THRESHOLD_PERCENT

    return volatility_threshold


def get_volatility_data_for_currencies(
    currency_codes: Set[str],
    minutes: int
) -> dict[str, VolatilityValue]:
    result = {}

    currency_code_map = get_currency_code_id_map()

    for currency_code in currency_codes:
        currency_id = currency_code_map.get(currency_code)
        if not currency_id:
            continue

        result.update({
            currency_code: get_volatility_data(
                currency_id=currency_id,
                minutes=minutes
            )
        })

    return result


def get_volatility_data(currency_id: str, minutes: int) -> VolatilityValue:
    prices_data = get_daily_currency_history(
        currency_id=currency_id,
    )

    sorted_prices_data = sorted(
        prices_data,
        key=lambda x: x.unix_timestamp,
        reverse=True
    )
    latest_value = sorted_prices_data[0].value

    index = minutes // STEP_MINUTES

    try:
        minutes_ago = sorted_prices_data[index].value
    except KeyError:
        raise Exception('error getting historical price')

    return VolatilityValue.calculate(minutes_ago, latest_value)


def check_candles(candles_count=None, threshold=None):
    from project.app import tg_bot
    candles_count = candles_count or 4
    threshold = threshold or 0.5

    redis = get_redis()
    chat_ids = redis.smembers(settings.CHATS_CACHE_KEY)

    if not chat_ids:
        return

    all_user_currencies = get_all_user_currencies(chat_ids)

    user_currency_codes = set()
    for curr in all_user_currencies.values():
        user_currency_codes.update(set(curr))

    all_currency_codes = default_currency_codes | user_currency_codes

    candle_data_by_currency = get_candles_data_for_currencies(
        currency_codes=all_currency_codes
    )

    for chat_id in chat_ids:
        user_currencies = all_user_currencies.get(chat_id, set())

        for currency in default_currency_codes | user_currencies:
            candle_data = candle_data_by_currency.get(currency)

            if not candle_data:
                continue

            latest_values = candle_data[-candles_count:]
            closes = [item.close for item in latest_values]

            is_downtrend = all(
                x < y
                for x, y in itertools.pairwise(closes)
            )
            is_uptrend = all(
                x > y
                for x, y in itertools.pairwise(closes)
            )

            volatility = VolatilityValue.calculate(closes[0], closes[-1])
            ratio = Ratio.get_ratio_display(volatility.ratio)

            if volatility.volatility < threshold:
                continue

            if not (is_uptrend or is_downtrend):
                continue

            message = (
                f'{currency}: {ratio} ({candles_count} candles), '
                f'{volatility.volatility}%'
            )
            tg_bot.send_message(
                chat_id=int(chat_id),
                text=message,
                parse_mode='HTML',
            )


def get_candles_data_for_currencies(
    currency_codes: Set[str]
):
    result = {}

    for currency_code in currency_codes:
        result.update({
            currency_code: get_ohlc(
                currency_code=currency_code,
            )
        })

    return result
