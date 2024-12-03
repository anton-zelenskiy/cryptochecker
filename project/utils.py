import functools
from typing import Callable, Any
import structlog
from collections import Counter
import datetime

logger = structlog.get_logger(__name__)


def error_handler(func: Callable) -> Callable:
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

    def stats(self) -> dict[str, Any]:
        counter = Counter(self._collector)
        
        if not counter:
            return {
                'top': 0,
                'avg': 0,
            }
        
        top_rpm = counter.most_common(1)[0]
        avg_rpm = counter.total() // len(list(counter))
        
        return {
            'top': (top_rpm[0], top_rpm[1]),
            'avg': avg_rpm
        }


rpm_counter = RequestCounter()


def request_counter(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        value = func(*args, **kwargs)
        rpm_counter.collect()
        
        logger.info('rpm:', stats=rpm_counter.stats())

        return value
    return wrapper
