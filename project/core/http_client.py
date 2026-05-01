from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from project.core.rate_limit import RateLimitExceeded, RateLimiter
from project.core.retry import Retry


logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    key: str
    limit: int
    window_s: int


class Http429RateLimitedError(Exception):
    pass


async def _get_json_once(
    client: httpx.AsyncClient,
    *,
    url: str,
    params: dict | None = None,
    headers: dict[str, str] | None = None,
    rate_limiter: RateLimiter | None = None,
    rate_limit: RateLimitPolicy | None = None,
) -> object:
    if rate_limiter is not None and rate_limit is not None:
        await rate_limiter.hit(key=rate_limit.key, limit=rate_limit.limit, window_s=rate_limit.window_s)

    r = await client.get(url, params=params, headers=headers)
    if r.status_code == 429:
        raise Http429RateLimitedError("429 Too Many Requests")

    r.raise_for_status()
    return r.json()


async def get_json(
    client: httpx.AsyncClient,
    *,
    url: str,
    params: dict | None = None,
    headers: dict[str, str] | None = None,
    rate_limiter: RateLimiter | None = None,
    rate_limit: RateLimitPolicy | None = None,
    max_attempts: int = 4,
    start_delay_s: float = 0.7,
    back_off: int = 2,
) -> object:
    def _on_retry(exc: BaseException, attempt: int, delay_s: float) -> None:
        logger.warning(
            "http retry",
            url=url,
            attempt=attempt,
            delay_s=delay_s,
            error=str(exc),
        )

    decorated = Retry(
        max_attempts=max_attempts,
        back_off=back_off,
        start_delay=start_delay_s,
        exceptions=(RateLimitExceeded, Http429RateLimitedError),
        on_retry=_on_retry,
    )(_get_json_once)

    return await decorated(
        client,
        url=url,
        params=params,
        headers=headers,
        rate_limiter=rate_limiter,
        rate_limit=rate_limit,
    )

