from pycoingecko import CoinGeckoAPI
from redis import Redis

from project.config import CHATS_CACHE_KEY, REDIS_HOST, REDIS_PORT
from project.api.telegram import TelegramAPI

cg = CoinGeckoAPI()
redis = Redis(host=REDIS_HOST, port=REDIS_PORT)
tg_api = TelegramAPI()


class Config:
    JOBS = [
        {
            'id': 'sent_currencies_price',
            'func': 'scheduler:send_currency_prices',
            'args': (),
            'trigger': 'interval',
            'minutes': 60
        }
    ]

    SCHEDULER_API_ENABLED = True


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
