import logging
from celery import shared_task

from .check_volatility import (
    send_currency_prices,
    check_volatility,
    check_candles,
)

logger = logging.getLogger(__name__)


# def register_jobs(scheduler):
#     scheduler.remove_all_jobs()
#     try:
#         # task_send_currency_prices(scheduler)
#         task_check_volatility(scheduler)
#         task_check_candles(scheduler)
#     except ConflictingIdError:
#         logger.info('conflicting jobs')
#         pass
#
#
# def task_send_currency_prices(scheduler):
#     scheduler.add_job(
#         send_currency_prices,
#         id='send_currency_prices',
#         jobstore='redis',
#         replace_existing=True,
#         trigger='cron',
#         hour='*/1',
#         args=[],
#     )
#
#
# def task_check_volatility(scheduler):
#     task_settings = (
#         (5, {'minute': '*/5'}),
#         (15, {'minute': '*/15'}),
#         (30, {'minute': '*/30'}),
#         (60, {'hour': '*/1'}),
#         (120, {'hour': '*/2'}),
#     )
#
#     for minutes, cron_time in task_settings:
#         scheduler.add_job(
#             check_volatility,
#             name=f'check_volatility_{minutes}',
#             id=f'check_volatility_{minutes}',
#             jobstore='redis',
#             replace_existing=True,
#             trigger='cron',
#             args=[minutes],
#             **cron_time,
#         )
#
#
# def task_check_candles(scheduler):
#     scheduler.add_job(
#         check_candles,
#         id='check_candles',
#         jobstore='redis',
#         replace_existing=True,
#         trigger='cron',
#         hour='*/1',
#         minute=2,
#         args=[],
#     )


@shared_task(queue='default')
def task_check_volatility(interval: int):
    check_volatility(interval)


@shared_task(queue='default')
def task_send_currency_prices():
    send_currency_prices()
