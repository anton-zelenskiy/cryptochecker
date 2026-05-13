from __future__ import annotations

import time
from typing import Protocol

from pydantic import BaseModel, PrivateAttr


class RateLimitExceeded(Exception):
    def __init__(self, *, key: str, limit: int, window_s: int) -> None:
        super().__init__(f"rate limit exceeded: {key} ({limit}/{window_s}s)")
        self.key = key
        self.limit = limit
        self.window_s = window_s


class RateLimiter(Protocol):
    async def hit(self, *, key: str, limit: int, window_s: int) -> None:
        """
        Record one hit for key in a fixed window.

        Raises RateLimitExceeded when over the limit.
        """


class InMemoryFixedWindowRateLimiter(BaseModel):
    _counters: dict[str, tuple[int, float]] = PrivateAttr(default_factory=dict)

    async def hit(self, *, key: str, limit: int, window_s: int) -> None:
        now = time.time()
        count, reset_at = self._counters.get(key, (0, now + window_s))
        if now >= reset_at:
            count, reset_at = 0, now + window_s

        count += 1
        self._counters[key] = (count, reset_at)
        if count > limit:
            raise RateLimitExceeded(key=key, limit=limit, window_s=window_s)


class RedisFixedWindowRateLimiter:
    def __init__(self, *, redis) -> None:
        self._redis = redis

    async def hit(self, *, key: str, limit: int, window_s: int) -> None:
        # Fixed window using INCR + EXPIRE. Best-effort and good enough for free-tier quotas.
        # Key is expected to include a namespace, e.g. "ratelimit:coingecko:markets".
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_s, nx=True)
        res = await pipe.execute()
        count = int(res[0] or 0)
        if count > limit:
            raise RateLimitExceeded(key=key, limit=limit, window_s=window_s)

