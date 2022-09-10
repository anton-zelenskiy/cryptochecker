from project import settings

from celery import Celery
from celery.schedules import crontab

celery = Celery(
    'project',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'project.scheduler.tasks',
    ]
)
celery.conf.update(app.config)
# app.autodiscover_tasks()

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
