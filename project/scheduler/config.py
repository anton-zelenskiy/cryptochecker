from pycoingecko import CoinGeckoAPI

from project.core.redis import get_redis
from project.api.telegram import TelegramAPI

cg = CoinGeckoAPI()
redis = get_redis()
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
