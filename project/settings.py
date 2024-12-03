import os


TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN', '')
ALPHAVANTAGE_API_KEY = os.getenv('ALPHAVANTAGE_API_KEY', '')

LOGGING_CONFIG = {
    'version': 1,
    'loggers': {
        '': {
            'level': 'INFO',
            'handlers': ['console_handler'],
        },
        'imp_calc': {
            'level': 'INFO',
            'handlers': ['console_handler'],
            'propagate': False,
        },
        'debug': {
            'level': 'INFO',
            'handlers': ['console_handler'],
            'propagate': False,
        },
    },
    'handlers': {
        'console_handler': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'formatter': 'simple'
        },
    },
    'formatters': {
        'simple': {
            'format': '%(pathname)s:%(lineno)d %(name)s %(asctime)s - %(levelname)s - %(message)s',
        },
    },
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
