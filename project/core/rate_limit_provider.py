from __future__ import annotations

from project.core.rate_limit import RedisFixedWindowRateLimiter, RateLimiter
from project.core.redis_async import get_redis


_limiter: RateLimiter | None = None


async def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        redis = await get_redis()
        _limiter = RedisFixedWindowRateLimiter(redis=redis)
    return _limiter

