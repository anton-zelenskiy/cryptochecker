import functools
from typing import Callable
import structlog
from collections import Counter
import datetime

logger = structlog.get_logger(__name__)


def error_handler(func: Callable):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f'Error occured: {str(e)}')
    return wrapper


class RequestCounter:
    def __init__(self) -> None:
        self._collector = []
        
    def collect(self):
        ts = datetime.datetime.now().replace(
            second=0,
            microsecond=0
        )
        self._collector.append(ts)

    def stats(self):
        return Counter(self._collector)


request_stat = RequestCounter()


def request_counter(func: Callable):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        value = func(*args, **kwargs)
        request_stat.collect()
        
        logger.info('request stats:', stat=request_stat.stats().most_common(3))

        return value
    return wrapper
