from pycoingecko import CoinGeckoAPI
from redis import Redis

from project.api.telegram import TelegramAPI
from project.api.alphavantage_api import AlphadvantageAPI, Ratio
from project.config import (
    CHATS_CACHE_KEY,
    REDIS_HOST,
    REDIS_PORT,
    VOLATILITY_THRESHOLD_PERCENT,
)

cg = CoinGeckoAPI()
redis = Redis(host=REDIS_HOST, port=REDIS_PORT, password='redis_password')
tg_api = TelegramAPI()


def send_currency_prices():
    """Notify subscribers about currency prices every hour."""
    chat_ids = redis.smembers(CHATS_CACHE_KEY)

    if not chat_ids:
        return

    currency_prices = cg.get_price(
        ids=['bitcoin', 'litecoin', 'ethereum'],
        vs_currencies='usd'
    )

    for chat_id in chat_ids:
        data = {
            'chat_id': int(chat_id),
            'text': get_currency_prices_display(currency_prices),
            'parse_mode': 'HTML'
        }
        tg_api.send_message(data)

    return currency_prices


def get_currency_prices_display(data):
    """Wraps info in html tags."""
    rows = []
    for k, v in data.items():
        rows.append(f"<i>{k}</i>: <b>{v['usd']}$</b>")

    return '\n'.join(rows)


def check_volatility():
    """Notify subscribers about currency volatility."""
    chat_ids = redis.smembers(CHATS_CACHE_KEY)

    if not chat_ids:
        return

    api = AlphadvantageAPI()

    currencies = ['BTC', 'ETH']

    for currency in currencies:
        volatility = api.get_volatility(currency=currency)

        for period_min, volatility_data in volatility.items():
            if volatility_data.volatility > VOLATILITY_THRESHOLD_PERCENT:
                ratio = Ratio.get_ratio_display(volatility_data.ratio)
                message = (
                    f'Price alert for {currency}. Period (min): {period_min}, '
                    f'volatility: {volatility_data.volatility} % ({ratio}), '
                    f'latest price: {volatility_data.latest_value}, '
                    f'old price: {volatility_data.old_value}'
                )
                send_message_to_subscribers(message)


def send_message_to_subscribers(message: str):
    chat_ids = redis.smembers(CHATS_CACHE_KEY)

    for chat_id in chat_ids:
        data = {
            'chat_id': int(chat_id),
            'text': message,
            'parse_mode': 'HTML'
        }
        tg_api.send_message(data)
