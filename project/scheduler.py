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
            'func': 'scheduler:sent_currencies_price',
            'args': (),
            'trigger': 'interval',
            'minutes': 1
        }
    ]

    SCHEDULER_API_ENABLED = True


def sent_currencies_price():
    """Отправляет подписчикам инфу о стоимости криптовалют.

    schedule:
    """
    chat_ids = redis.smembers(CHATS_CACHE_KEY)

    if not chat_ids:
        return

    result = cg.get_price(
        ids=['bitcoin', 'litecoin', 'ethereum'],
        vs_currencies='usd'
    )

    for chat_id in chat_ids:
        data = {
            'chat_id': int(chat_id),
            'text': parse_currencies(result),
            'parse_mode': 'HTML'
        }
        tg_api.send_message(data)

    return result


def parse_currencies(data):
    """Возвращает информацию в html-разметке. """
    rows = []
    for k, v in data.items():
        rows.append(f"<i>{k}</i>: <b>{v['usd']}$</b>")

    return '<br>'.join(rows)
