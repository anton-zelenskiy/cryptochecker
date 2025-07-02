import structlog
from celery import shared_task

from .check_volatility import (
    send_currency_prices,
    check_volatility,
    check_candles,
)

logger = structlog.get_logger(__name__)


@shared_task(queue='default')
def task_check_volatility(interval: int):
    check_volatility(interval)


@shared_task(queue='default')
def task_send_currency_prices():
    send_currency_prices()


@shared_task(queue='default')
def task_check_candles(candles_count: int = 4, threshold: float = 1.0):
    check_candles(candles_count, threshold)
