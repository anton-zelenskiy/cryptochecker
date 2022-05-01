import os
import logging


logging.getLogger('parso.python.diff').disabled = True


API_TOKEN = os.getenv('API_TOKEN', '')

LOGGING_CONFIG = {
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'formatter': 'default'
    }},
    'root': {
        'level': 'DEBUG',
        'handlers': ['wsgi']
    }
}

WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', '')
WEBHOOK_PORT = os.getenv('WEBHOOK_PORT', 443)


REDIS_HOST = 'redis'
REDIS_PORT = 6379
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', 'redis_password')
CHATS_CACHE_KEY = 'chats'


ALPHAVANTAGE_API_KEY = '7LWBNDGBH88CCQPG'

VOLATILITY_THRESHOLD_PERCENT = 4
