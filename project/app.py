import telebot
import json

from flask import Flask, request
from logging.config import dictConfig

from project.api.telegram import TelegramAPI
from project.config import API_TOKEN, DICT_CONFIG, WEBHOOK_HOST, WEBHOOK_PORT
from project.utils import parse_update


dictConfig(DICT_CONFIG)

WEBHOOK_URL_BASE = f'https://{WEBHOOK_HOST}:{WEBHOOK_PORT}'
WEBHOOK_URL_PATH = f'/{API_TOKEN}/'

bot = telebot.TeleBot(API_TOKEN)

app = Flask(__name__)

tg_api = TelegramAPI()


@app.route('/', methods=['GET', 'HEAD'])
def index():
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

    data = {
        'chat_id': update.message.chat.id,
        'text': 'Привет!',
        'reply_markup': {
            'keyboard': ['/ss']
        }
    }
    if update.message.text in ['/start', '/help']:
        tg_api.send_message(data)

    elif update.message.text == '/ss':
        tg_api.send_message({
            'chat_id': update.message.chat.id,
            'text': 'Кликнул по кнопке!',
        })

    # app.logger.info(request.get_data().decode('utf-8'))
    return ''


# # Process webhook calls
# @app.route(WEBHOOK_URL_PATH, methods=['POST'])
# def webhook():
#     if flask.request.headers.get('content-type') == 'application/json':
#         json_string = flask.request.get_data().decode('utf-8')
#         update = telebot.types.Update.de_json(json_string)
#         bot.process_new_updates([update])
#         return ''
#     else:
#         flask.abort(403)
#
#
# # Handle '/start' and '/help'
# @bot.message_handler(commands=['help', 'start'])
# def send_welcome(message):
#     bot.reply_to(message,
#                  ("Hi there, I am EchoBot.\n"
#                   "I am here to echo your kind words back to you."))
#
#
# # Handle all other messages
# @bot.message_handler(func=lambda message: True, content_types=['text'])
# def echo_message(message):
#     bot.reply_to(message, message.text)


if __name__ == '__main__':
    app.run(debug=True)
