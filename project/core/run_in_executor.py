import asyncio
from collections.abc import Awaitable, Callable
import contextvars
import functools
import threading
from typing import Any

import structlog


logger = structlog.get_logger(__name__)


def run_in_executor(fn: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
    if asyncio.iscoroutinefunction(fn):
        return fn

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Awaitable[Any]:
        labels = {'function_name': fn.__name__}

        def blocking_io(*b_args: Any, **b_kwargs: dict[str, str]) -> Any:
            logger.info('blocking task was started', **labels)
            result = fn(*b_args, **b_kwargs)
            logger.info('blocking task was completed', **labels)
            return result

        assert threading.current_thread() is threading.main_thread()
        loop = asyncio.get_running_loop()

        # allow to use contextvars with thread pool
        context = contextvars.copy_context()
        blocking_with_context = functools.partial(
            blocking_io,
            *args,
            **kwargs,
        )
        return await loop.run_in_executor(None, context.run, blocking_with_context)

    return wrapper
