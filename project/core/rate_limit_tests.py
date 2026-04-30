from __future__ import annotations

import pytest

from project.core.rate_limit import InMemoryFixedWindowRateLimiter, RateLimitExceeded


@pytest.mark.asyncio
async def test_inmemory_fixed_window_blocks_over_limit() -> None:
    limiter = InMemoryFixedWindowRateLimiter()
    await limiter.hit(key="k", limit=2, window_s=60)
    await limiter.hit(key="k", limit=2, window_s=60)
    with pytest.raises(RateLimitExceeded):
        await limiter.hit(key="k", limit=2, window_s=60)

