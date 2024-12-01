import os
import logging


logging.getLogger('parso.python.diff').disabled = True


TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN', '')

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

CELERY_BROKER_URL = os.environ.get(
    'CELERY_BROKER_URL',
    'redis://redis:6379/1'
)
CELERY_RESULT_BACKEND = os.environ.get(
    'CELERY_RESULT_BACKEND',
    'redis://redis:6379/1'
)
CELERY_TIMEZONE = 'Asia/Tomsk'


ALPHAVANTAGE_API_KEY = '7LWBNDGBH88CCQPG'
