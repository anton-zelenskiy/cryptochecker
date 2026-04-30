from __future__ import annotations

import pytest
import httpx

from project.core.http_client import RateLimitPolicy, get_json_with_retries
from project.core.rate_limit import InMemoryFixedWindowRateLimiter, RateLimitExceeded


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit() -> None:
    limiter = InMemoryFixedWindowRateLimiter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True}))) as c:
        policy = RateLimitPolicy(key="ratelimit:test", limit=1, window_s=60)
        await get_json_with_retries(c, url="https://example.com", rate_limiter=limiter, rate_limit=policy)
        with pytest.raises(RateLimitExceeded):
            await get_json_with_retries(c, url="https://example.com", rate_limiter=limiter, rate_limit=policy, max_attempts=1)


@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(429, json={"error": "rl"})
        return httpx.Response(200, json={"data": 1})

    # speed up test (no real sleep)
    async def no_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr("project.core.http_client.asyncio.sleep", no_sleep)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        data = await get_json_with_retries(c, url="https://example.com", max_attempts=3)
    assert data == {"data": 1}
    assert calls["n"] == 2

