from pycoingecko import CoinGeckoAPI

from project.config import CHATS_CACHE_KEY
from project.app import tg_api, redis

cg = CoinGeckoAPI()


class Config:
    JOBS = [
        {
            'id': 'sent_currencies_price',
            'func': 'scheduler:sent_currencies_price',
            'args': (),
            'trigger': 'interval',
            'seconds': 30
        }
    ]

    SCHEDULER_API_ENABLED = True


def sent_currencies_price():
    """Отправляет подписчикам инфу о стоимости криптовалют.

    schedule:
    """
    chat_ids = redis.get(CHATS_CACHE_KEY)

    result = cg.get_price(
        ids=['bitcoin', 'litecoin', 'ethereum'],
        vs_currencies='usd'
    )

    for chat_id in chat_ids:
        data = {
            'chat_id': chat_id,
            'text': result
        }
        tg_api.send_message(data)

    return result
