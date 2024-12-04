import functools
from typing import Callable, Any
import structlog
import operator
import datetime
from project.core.redis import get_redis

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
    KEY_RPS = 'stats:rps'
    
    def __init__(self) -> None:
        self._redis = get_redis()
        
    def collect(self):
        ts = datetime.datetime.now().replace(
            second=0,
            microsecond=0
        )

        self._redis.hincrby(
            self.KEY_RPS,
            ts.isoformat(),
            1
        )

    def stats(self) -> dict[str, Any]:
        data = self._redis.hgetall(self.KEY_RPS) or {}
        
        top_rpm = max(data.items(), key=operator.itemgetter(1))
        avg_rpm = sum([int(i) for i in data.values()]) // len(data)
        
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
