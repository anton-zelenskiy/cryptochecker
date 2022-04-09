from pycoingecko import CoinGeckoAPI
from typing import Iterable, Set

from project.core.redis import get_redis
from project import settings
from project.api.alphavantage_api import AlphadvantageAPI, Ratio

cg = CoinGeckoAPI()


def send_currency_prices():
    """Notify subscribers about currency prices every hour."""
    from project.app import tg_bot

    redis = get_redis()
    chat_ids = redis.smembers(settings.CHATS_CACHE_KEY)

    if not chat_ids:
        return

    currency_prices = cg.get_price(
        ids=['bitcoin', 'ethereum', 'cardano', 'terra-luna'],
        vs_currencies='usd'
    )

    for chat_id in chat_ids:
        tg_bot.send_message(
            chat_id=int(chat_id),
            text=get_currency_prices_display(currency_prices),
            parse_mode='HTML',
        )

    return currency_prices


def get_currency_prices_display(data):
    """Wraps info in html tags."""
    rows = []
    for k, v in data.items():
        rows.append(f"<i>{k}</i>: <b>{v['usd']}$</b>")

    return '\n'.join(rows)


def check_volatility():
    """Notify subscribers about currency volatility."""
    from project.app import tg_bot

    redis = get_redis()
    chat_ids = redis.smembers(settings.CHATS_CACHE_KEY)

    if not chat_ids:
        return

    currencies = ['BTC', 'ETH']
    user_currencies_data = get_user_currencies_data(chat_ids)

    all_currencies = set(currencies)
    all_currencies.update({
        set(curr) for curr in user_currencies_data.values()
        if curr
    })

    volatility_data_by_currency = get_volatility_data(all_currencies)

    for chat_id in chat_ids:
        user_currencies = user_currencies_data.get(chat_id, set())
        volatility_threshold = get_volatility_threshold(chat_id)

        for currency in set(currencies) | set(user_currencies):
            volatility = volatility_data_by_currency.get(currency)

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


def get_user_currencies_data(chat_ids: Iterable[str]):
    redis = get_redis()

    result = {}
    for chat_id in chat_ids:
        result.update({
            chat_id: redis.smembers(
                f'volatility:user:{chat_id}:currencies'
            ) or []
        })
    return result


def get_volatility_threshold(chat_id):
    redis = get_redis()

    try:
        volatility_threshold = float(
            redis.get(f'volatility:user:{chat_id}:threshold')
        )
    except TypeError:
        volatility_threshold = settings.VOLATILITY_THRESHOLD_PERCENT

    return volatility_threshold


def get_volatility_data(currencies: Set[str]):
    result = {}

    api = AlphadvantageAPI()

    for currency in currencies:
        result.update({
            currency: api.get_volatility(currency=currency)
        })

    return result
