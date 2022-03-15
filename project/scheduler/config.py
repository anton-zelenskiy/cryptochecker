from pycoingecko import CoinGeckoAPI
from redis import Redis

from project.api.telegram import TelegramAPI
from project.config import REDIS_HOST, REDIS_PORT

cg = CoinGeckoAPI()
redis = Redis(host=REDIS_HOST, port=REDIS_PORT, password='redis_password')
tg_api = TelegramAPI()


class Config:
    JOBS = [
        {
            'id': 'sent_currencies_price',
            'func': 'project.scheduler.tasks:send_currency_prices',
            'args': (),
            'trigger': 'interval',
            'minutes': 60
        },
        {
            'id': 'check_volatility',
            'func': 'project.scheduler.tasks:check_volatility',
            'args': (),
            'trigger': 'interval',
            'minutes': 5,
        },
    ]

    SCHEDULER_API_ENABLED = True
