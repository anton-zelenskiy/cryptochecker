import logging

from apscheduler.jobstores.base import ConflictingIdError

from .check_volatility import (
    send_currency_prices,
    check_volatility,
)

logger = logging.getLogger(__name__)


def register_jobs(scheduler):
    try:
        task_send_currency_prices(scheduler)
        task_check_volatility(scheduler)
    except ConflictingIdError:
        logger.info('conflicting jobs')
        pass


def task_send_currency_prices(scheduler):
    scheduler.add_job(
        send_currency_prices,
        id='send_currency_prices',
        jobstore='redis',
        replace_existing=True,
        trigger='cron',
        hour='*/1',
        args=[],
    )


def task_check_volatility(scheduler):
    minutes_ago = [5, 15, 30, 60, 120]
    for minutes in minutes_ago:
        scheduler.add_job(
            check_volatility,
            id=f'check_volatility_{minutes}',
            jobstore='redis',
            replace_existing=True,
            trigger='cron',
            minute=f'*/{minutes}',
            args=[minutes],
        )
