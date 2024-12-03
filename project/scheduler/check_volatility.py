import itertools
import structlog

from project.api.coingecko import (
    CoingeckoMarketAPI,
)
from project.currencies.structures import Coin, Ratio, VolatilityValue
from project import constants
from project.core.redis import SettingStorage

setting_storage = SettingStorage()

market_api = CoingeckoMarketAPI()

logger = structlog.get_logger(__name__)

default_currency_codes = {"btc", "eth"}


def send_currency_prices():
    """Notify subscribers about currency prices every hour."""
    from project.app import tg_bot

    chat_ids = setting_storage.get_chat_ids()
    if not chat_ids:
        return

    all_user_currencies = setting_storage.get_all_user_currencies(chat_ids)

    user_currency_codes = set()
    for curr in all_user_currencies.values():
        user_currency_codes.update(set(curr))

    all_currency_codes = default_currency_codes | user_currency_codes

    currency_prices = market_api.get_currency_prices(currency_codes=all_currency_codes)

    for chat_id in chat_ids:
        user_currencies = all_user_currencies.get(chat_id, [])
        user_currency_prices = [
            item
            for item in currency_prices
            if item.currency_code in default_currency_codes | user_currencies
        ]

        tg_bot.send_message(
            chat_id=int(chat_id),
            text=Coin.display(
                user_currency_prices, constants.DEFAULT_VOLATILITY_THRESHOLD_PERCENT
            ),
            parse_mode="HTML",
        )

    return currency_prices


def check_volatility(minutes: int):
    """Notify subscribers about currency volatility."""
    from project.app import tg_bot

    chat_ids = setting_storage.get_chat_ids()
    if not chat_ids:
        return

    all_user_currencies = setting_storage.get_all_user_currencies(chat_ids)

    user_currency_codes = set()
    for curr in all_user_currencies.values():
        user_currency_codes.update(set(curr))

    all_currency_codes = default_currency_codes | user_currency_codes

    volatility_data_by_currency = get_volatility_data_for_currencies(
        currency_codes=all_currency_codes, minutes=minutes
    )

    for chat_id in chat_ids:
        user_currencies = all_user_currencies.get(chat_id, set())
        volatility_threshold = setting_storage.get_volatility_threshold(chat_id)

        for currency in default_currency_codes | user_currencies:
            volatility = volatility_data_by_currency.get(currency)

            if not volatility:
                continue

            if volatility.volatility > volatility_threshold:
                tg_bot.send_message(
                    chat_id=int(chat_id),
                    text=volatility.display(
                        currency=currency,
                        minutes_window=minutes,
                        percentage=constants.DEFAULT_VOLATILITY_THRESHOLD_PERCENT,
                    ),
                    parse_mode="HTML",
                )


def get_volatility_data_for_currencies(
    currency_codes: set[str], minutes: int
) -> dict[str, VolatilityValue]:
    result = {}

    for currency_code in currency_codes:
        result.update(
            {
                currency_code: get_volatility_data(
                    currency_code=currency_code,
                    minutes=minutes
                )
            }
        )

    return result


def get_volatility_data(currency_code: str, minutes: int) -> VolatilityValue:
    prices_data = market_api.get_history_price(currency_code)

    sorted_prices_data = sorted(
        prices_data, key=lambda x: x.unix_timestamp, reverse=True
    )
    latest_value = sorted_prices_data[0].value

    index = minutes // constants.STEP_MINUTES

    try:
        minutes_ago = sorted_prices_data[index].value
    except KeyError:
        raise Exception("error getting historical price")

    return VolatilityValue.calculate(minutes_ago, latest_value)


def check_candles(candles_count=None, threshold=None):
    from project.app import tg_bot

    candles_count = candles_count or 4
    threshold = threshold or 0.5

    chat_ids = setting_storage.get_chat_ids()
    if not chat_ids:
        return

    all_user_currencies = setting_storage.get_all_user_currencies(chat_ids)

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

            is_downtrend = all(x < y for x, y in itertools.pairwise(closes))
            is_uptrend = all(x > y for x, y in itertools.pairwise(closes))

            volatility = VolatilityValue.calculate(closes[0], closes[-1])
            ratio = Ratio.get_ratio_display(volatility.ratio)

            if volatility.volatility < threshold:
                continue

            if not (is_uptrend or is_downtrend):
                continue

            message = (
                f"{currency}: {ratio} ({candles_count} candles), "
                f"{volatility.volatility}%"
            )
            tg_bot.send_message(
                chat_id=int(chat_id),
                text=message,
                parse_mode="HTML",
            )


def get_candles_data_for_currencies(currency_codes: set[str]):
    result = {}

    for currency_code in currency_codes:
        result.update(
            {
                currency_code: market_api.get_ohlc(
                    currency_code=currency_code,
                )
            }
        )

    return result
