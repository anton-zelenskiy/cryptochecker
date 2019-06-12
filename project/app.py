from flask import Flask
import time
import flask
import logging
import telebot

from project.api.telegram import TelegramAPI

API_TOKEN = '825274529:AAFZVv3DYYmCvSBUl8HI3D8FbhiCNSudMvc'
WEBHOOK_HOST = 'zstoreit.info'
WEBHOOK_PORT = 80

WEBHOOK_URL_BASE = f'https://{WEBHOOK_HOST}:{WEBHOOK_PORT}'
WEBHOOK_URL_PATH = f'/{API_TOKEN}/'

bot = telebot.TeleBot(API_TOKEN)
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

app = Flask(__name__)

tg_api = TelegramAPI()


# Empty webserver index, return nothing, just http 200
@app.route('/', methods=['GET', 'HEAD'])
def index():
    bot.remove_webhook()
    time.sleep(0.1)
    bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH, max_connections=1)

    return 'Hi there!'


@app.route(f'{WEBHOOK_URL_PATH}get', methods=['GET'])
def get_w():
    res = tg_api.get_webhook_info()

    return f'Get-Result: {res}'


@app.route(f'{WEBHOOK_URL_PATH}set', methods=['GET'])
def set_w():
    res = tg_api.set_webhook()

    return f'Set-Result: {res}'


@app.route(f'{WEBHOOK_URL_PATH}delete', methods=['GET'])
def set_w():
    res = tg_api.delete_webhook()

    return f'Delete-Result: {res}'


# Process webhook calls
@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)


# Handle '/start' and '/help'
@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    bot.reply_to(message,
                 ("Hi there, I am EchoBot.\n"
                  "I am here to echo your kind words back to you."))


# Handle all other messages
@bot.message_handler(func=lambda message: True, content_types=['text'])
def echo_message(message):
    bot.reply_to(message, message.text)


if __name__ == '__main__':
    app.run()