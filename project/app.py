import atexit
from logging.config import dictConfig

import telegram
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request

from project import settings
from project.dispatcher import init_dispatcher
from project.scheduler import register_jobs

dictConfig(settings.LOGGING_CONFIG)

WEBHOOK_URL_BASE = f'https://{settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}'
WEBHOOK_URL_PATH = f'/{settings.API_TOKEN}/'

tg_bot = telegram.Bot(settings.API_TOKEN)
tg_bot.set_webhook(url=f'{WEBHOOK_URL_BASE}{WEBHOOK_URL_PATH}')
dispatcher = init_dispatcher(bot=tg_bot)


def create_app():
    app = Flask(__name__)

    scheduler = BackgroundScheduler(
        {'apscheduler.timezone': 'Asia/Tbilisi'},
        jobstores={
            'redis': RedisJobStore(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
            ),
        },
        daemon=True,
    )
    register_jobs(scheduler)
    if not scheduler.running:
        scheduler.start()

    atexit.register(lambda: scheduler.shutdown())

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

    return app


app = create_app()


if __name__ == '__main__':
    app.run(use_reloader=False)
