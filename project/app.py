import atexit
import logging
from logging.config import dictConfig
import telegram
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request

from project import settings
from project.dispatcher import init_dispatcher
# from project.scheduler import register_jobs

from project import settings

from celery import Celery
from celery.schedules import crontab

task_default_queue = 'default'

CELERY_TIMEZONE = 'Asia/Tbilisi'

broker_url = settings.CELERY_BROKER_URL
result_backend = settings.CELERY_RESULT_BACKEND

beat_schedule = {
    'task_check_volatility': {
        'task': 'project.scheduler.tasks.task_check_volatility',
        'schedule': crontab(minute='*/5'),
        'args': (5,)
    },
    'task_send_currency_prices': {
        'task': 'project.scheduler.tasks.task_send_currency_prices',
        'schedule': crontab(minute='*/1')
    },
}


dictConfig(settings.LOGGING_CONFIG)

WEBHOOK_URL_BASE = f'https://{settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}'
WEBHOOK_URL_PATH = f'/{settings.API_TOKEN}/'

tg_bot = telegram.Bot(settings.API_TOKEN)
# tg_bot.set_webhook(url=f'{WEBHOOK_URL_BASE}{WEBHOOK_URL_PATH}')
dispatcher = init_dispatcher(bot=tg_bot)

logger = logging.getLogger(__name__)

app = Flask(__name__)

celery = Celery(
    'project',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['project.scheduler.tasks']
)
# celery.conf.update(app.config)
celery.autodiscover_tasks()


@app.route('/', methods=['GET', 'HEAD'])
def index():
    return 'Hi there!'


@app.route(f'{WEBHOOK_URL_PATH}get/', methods=['GET'])
def get_webhook_info():
    res = tg_bot.get_webhook_info()

    return f'Get-Result: {res}'


@app.route(f'{WEBHOOK_URL_PATH}getMe/', methods=['GET'])
def get_me():
    res = tg_bot.get_me()

    return f'Get-Result: {res}'


@app.route(f'{WEBHOOK_URL_PATH}delete/', methods=['GET'])
def delete_webhook():
    res = tg_bot.delete_webhook()

    return f'Delete-Result: {res}'


@app.route(f'{WEBHOOK_URL_PATH}', methods=['POST'])
def updates():
    update = telegram.update.Update.de_json(
        request.get_json(force=True),
        bot=tg_bot,
    )
    dispatcher.process_update(update)

    return ''


if __name__ == '__main__':
    app.run(use_reloader=False)
