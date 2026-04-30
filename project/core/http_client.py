from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

import httpx
import structlog

from project.core.rate_limit import RateLimitExceeded, RateLimiter


logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    key: str
    limit: int
    window_s: int


def _jittered_sleep_s(base: float) -> float:
    return base * (0.7 + random.random() * 0.6)


async def get_json_with_retries(
    client: httpx.AsyncClient,
    *,
    url: str,
    params: dict | None = None,
    headers: dict[str, str] | None = None,
    rate_limiter: RateLimiter | None = None,
    rate_limit: RateLimitPolicy | None = None,
    max_attempts: int = 4,
    start_delay_s: float = 0.7,
) -> object:
    delay = start_delay_s
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            if rate_limiter is not None and rate_limit is not None:
                await rate_limiter.hit(
                    key=rate_limit.key, limit=rate_limit.limit, window_s=rate_limit.window_s
                )

            r = await client.get(url, params=params, headers=headers)
            if r.status_code == 429:
                raise httpx.HTTPStatusError("429 Too Many Requests", request=r.request, response=r)
            if 500 <= r.status_code <= 599:
                raise httpx.HTTPStatusError(f"{r.status_code} Server Error", request=r.request, response=r)

            r.raise_for_status()
            return r.json()

        except (RateLimitExceeded, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            last_exc = e
            if attempt >= max_attempts:
                break
            logger.warning(
                "http retry",
                url=url,
                attempt=attempt,
                error=str(e),
            )
            await asyncio.sleep(_jittered_sleep_s(delay))
            delay *= 2

    assert last_exc is not None
    raise last_exc

