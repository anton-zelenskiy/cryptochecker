import redis
from project import settings
from functools import lru_cache


@lru_cache()
def get_redis():
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        # password='redis_password',
        decode_responses=True,
    )
