import redis.asyncio as redis

from project.core.config import settings


_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    """Close the shared client (e.g. on app shutdown)."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
