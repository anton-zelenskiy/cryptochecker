import asyncio
from collections.abc import Callable
import functools
from typing import Any

import structlog


logger = structlog.get_logger(__name__)


class Retry:
    """Retry decorator for async functions."""

    def __init__(
        self,
        max_attempts: int = 3,
        back_off: int = 2,
        start_delay: int = 0.5,
        exceptions: tuple[Exception, ...] | None = None,
    ) -> None:
        self._max_attempts = max_attempts
        self._back_off = back_off
        self._start_delay = start_delay
        self._exceptions = exceptions or Exception

    def __call__(self, fn: Callable) -> Callable:
        assert asyncio.iscoroutinefunction(fn)  # noqa: S101

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            time_to_sleep = self._start_delay
            for _ in range(1, self._max_attempts):
                try:
                    return await fn(*args, **kwargs)
                except self._exceptions:
                    await asyncio.sleep(time_to_sleep)
                    time_to_sleep *= self._back_off

            return await fn(*args, **kwargs)

        return wrapper


retry = Retry
