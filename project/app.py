import logging
from logging.config import dictConfig

import telegram
from flask import Flask, request

from project import settings
from project.celery_app import make_celery, CELERY_CONFIG
from project.dispatcher import init_dispatcher

dictConfig(settings.LOGGING_CONFIG)

WEBHOOK_URL_BASE = f'https://{settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}'
WEBHOOK_URL_PATH = f'/{settings.API_TOKEN}/'

tg_bot = telegram.Bot(settings.API_TOKEN)

dispatcher = init_dispatcher(bot=tg_bot)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.update(CELERY_CONFIG=CELERY_CONFIG)
celery = make_celery(app)


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


@app.route(f'{WEBHOOK_URL_PATH}set/', methods=['GET'])
def set_webhook():
    res = tg_bot.set_webhook(
        url=f'{WEBHOOK_URL_BASE}{WEBHOOK_URL_PATH}',
        certificate=open('certificate.pem', 'rb')
    )
    return f'{str(res)}'


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
