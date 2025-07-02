from project import settings

from celery import Celery
from celery.schedules import crontab


CELERY_CONFIG = {
    'broker_url': settings.CELERY_BROKER_URL,
    'result_backend': settings.CELERY_RESULT_BACKEND,
    'beat_schedule': {
        'task_check_volatility_5': {
            'task': 'project.scheduler.tasks.task_check_volatility',
            'schedule': crontab(minute='*/5'),
            'args': (5,)
        },
        'task_check_volatility_15': {
            'task': 'project.scheduler.tasks.task_check_volatility',
            'schedule': crontab(minute='*/15'),
            'args': (15,)
        },
        'task_check_volatility_30': {
            'task': 'project.scheduler.tasks.task_check_volatility',
            'schedule': crontab(minute='*/30'),
            'args': (30,)
        },
        'task_check_volatility_60': {
            'task': 'project.scheduler.tasks.task_check_volatility',
            'schedule': crontab(hour='*/1', minute=1),
            'args': (60,)
        },
        'task_check_volatility_240': {
            'task': 'project.scheduler.tasks.task_check_volatility',
            'schedule': crontab(hour='*/4', minute=1),
            'args': (240,)
        },
        # 'task_send_currency_prices': {
        #     'task': 'project.scheduler.tasks.task_send_currency_prices',
        #     'schedule': crontab(hour='*/4', minute=0)
        # },
        'task_check_candles_4_1': {
            'task': 'project.scheduler.tasks.task_check_candles',
            'schedule': crontab(minute=5),
            'args': (4, 1),
        },
    },
    'task_default_queue': 'default',
    'task_ignore_result': True,
}


def make_celery(app):
    celery = Celery(
        'project',
        include=[
            'project.scheduler.tasks',
        ]
    )
    celery.conf.update(app.config['CELERY_CONFIG'])

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
