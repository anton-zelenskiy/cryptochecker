import telebot
import json
from redis import Redis
from flask_apscheduler import APScheduler
from pycoingecko import CoinGeckoAPI
from flask import Flask, request
from logging.config import dictConfig

from project.api.telegram import TelegramAPI
from project.utils import parse_update
from project.scheduler import Config

from project.config import (
    API_TOKEN,
    DICT_CONFIG,
    WEBHOOK_HOST,
    WEBHOOK_PORT,
    CHATS_CACHE_KEY,
)


dictConfig(DICT_CONFIG)

WEBHOOK_URL_BASE = f'https://{WEBHOOK_HOST}:{WEBHOOK_PORT}'
WEBHOOK_URL_PATH = f'/{API_TOKEN}/'

bot = telebot.TeleBot(API_TOKEN)

app = Flask(__name__)
app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

tg_api = TelegramAPI()

redis = Redis(host='redis', port=6379)


# console log: app.logger.info(request.get_data().decode('utf-8'))

@app.route('/', methods=['GET', 'HEAD'])
def index():
    redis.incr('test:key')
    app.logger.info(f"key: {redis.get('test:key')}")
    return 'Hi there!'


@app.route(f'{WEBHOOK_URL_PATH}get/', methods=['GET'])
def get_me():
    res = tg_api.get_webhook_info()

    return f'Get-Result: {res}'


@app.route(f'{WEBHOOK_URL_PATH}getMe/', methods=['GET'])
def get_w():
    res = tg_api.get_me()

    return f'Get-Result: {res}'


@app.route(f'{WEBHOOK_URL_PATH}set/', methods=['GET'])
def set_w():
    params = {
        'url': f'{WEBHOOK_URL_BASE}{WEBHOOK_URL_PATH}updates/'
    }
    res = tg_api.set_webhook(params)

    return f'Set-Result: {res}'


@app.route(f'{WEBHOOK_URL_PATH}delete/', methods=['GET'])
def del_w():
    res = tg_api.delete_webhook()

    return f'Delete-Result: {res}'


@app.route(f'{WEBHOOK_URL_PATH}updates/', methods=['POST'])
def updates():
    if not request.headers.get('content-type') == 'application/json':
        return 'Unexpected ContentType', 400

    response = json.loads(request.get_data())
    update = parse_update(response)

    save_client_info(update)
    send_message(update)
    return ''


def save_client_info(update):
    """Сохраняет id чата и id пользователя. """

    chat_ids = redis.get(CHATS_CACHE_KEY) or []
    chat_ids.append(update.message.chat.id)

    redis.set(CHATS_CACHE_KEY, chat_ids)


def send_message(update):
    """Отправляет сообщение в чат. """

    keyboard = json.dumps({
        'keyboard': [
            [{'text': 'bitcoin'}], [{'text': 'ethereum'}],
            [{'text': 'ripple'}], [{'text': 'litecoin'}],
        ]
    })

    data = {
        'chat_id': update.message.chat.id,
    }
    cg = CoinGeckoAPI()

    if update.message.text in ('/start', '/help',):
        data.update({'reply_markup': keyboard})
        tg_api.send_message(data)

    elif update.message.text == 'bitcoin':
        result = cg.get_price(ids=['bitcoin'], vs_currencies='usd')
        data.update({'text': result})
        tg_api.send_message(data)

    elif update.message.text == 'ethereum':
        result = cg.get_price(ids=['ethereum'], vs_currencies='usd')
        data.update({'text': result})
        tg_api.send_message(data)

    elif update.message.text == 'ripple':
        result = cg.get_price(ids=['ripple'], vs_currencies='usd')
        data.update({'text': result})
        tg_api.send_message(data)

    elif update.message.text == 'litecoin':
        result = cg.get_price(ids=['litecoin'], vs_currencies='usd')
        data.update({'text': result})
        tg_api.send_message(data)

    else:
        data = {
            'chat_id': update.message.chat.id,
            'text': 'Попробуйте другую команду'
        }
        tg_api.send_message(data)


if __name__ == '__main__':
    app.run(debug=True)
