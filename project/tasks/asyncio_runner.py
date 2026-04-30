from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

_T = TypeVar("_T")

_loop: asyncio.AbstractEventLoop | None = None


def run(coro: Coroutine[Any, Any, _T]) -> _T:
    """
    Run an async coroutine from Celery's sync task context.

    Important: do NOT use asyncio.run() in Celery tasks, because it creates a new loop
    per invocation, and async resources (asyncpg pools, engines, clients) are often
    bound to the loop that created them.
    """
    global _loop

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("asyncio_runner.run() called from a running event loop")

    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)

    return _loop.run_until_complete(coro)

