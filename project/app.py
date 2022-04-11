from logging.config import dictConfig

import telegram
from flask import Flask, request
from flask_apscheduler import APScheduler

from project import settings
from project.dispatcher import init_dispatcher
from project.scheduler.config import (
    Config,
    cron_send_currencies_price,
    cron_check_volatility,
)
from project.scheduler.tasks import (
    send_currency_prices,
    check_volatility,
)

dictConfig(settings.LOGGING_CONFIG)

WEBHOOK_URL_BASE = f'https://{settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}'
WEBHOOK_URL_PATH = f'/{settings.API_TOKEN}/'

app = Flask(__name__)
app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()
scheduler.add_job(send_currency_prices, cron_send_currencies_price)
scheduler.add_job(check_volatility, cron_check_volatility)

tg_bot = telegram.Bot(settings.API_TOKEN)
tg_bot.set_webhook(url=f'{WEBHOOK_URL_BASE}{WEBHOOK_URL_PATH}')
dispatcher = init_dispatcher(bot=tg_bot)


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
    app.run()
