import datetime
import functools
import operator
import time
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

from project.core.redis import get_redis

Func = TypeVar('Func', bound=Callable[..., Any])

logger = structlog.get_logger(__name__)


def error_handler(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f'Error occured: {str(e)}')
    return wrapper


def retry(
    exception_to_check: type[Exception] | tuple[type[Exception], ...],
    exception_matches: list[str] | None = None,
    tries: int = 4,
    delay: int = 3,
    backoff: int = 2,
) -> Callable[[Func], Func]:
    def deco_retry(func: Func) -> Func:
        @functools.wraps(func)
        def f_retry(*args: Any, **kwargs: Any) -> Func:
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exception_to_check as ex:
                    if exception_matches:
                        if not any(i in str(ex) for i in exception_matches):
                            raise ex

                    logger.info(
                        f'{ex.__class__.__name__}: {ex} raised in {func.__name__}.'
                        f' Retrying in {mdelay} seconds.'
                    )

                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)

        return f_retry # type: ignore

    return deco_retry


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
        try:
            rpm_counter.collect()
            logger.info('rpm:', stats=rpm_counter.stats())
        except Exception as e:
            logger.error(f'Error occured: {str(e)}')

        return value
    return wrapper
