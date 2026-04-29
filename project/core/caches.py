from collections.abc import Awaitable, Callable
import functools
import hashlib
import json
from operator import attrgetter
from typing import Any, ParamSpec, TypeVar

from aiocache import Cache
from aiocache.serializers import PickleSerializer
import structlog

from project.core.config import settings


logger = structlog.get_logger(__name__)

P = ParamSpec('P')
R = TypeVar('R')


_cache = Cache(
    Cache.REDIS,
    endpoint=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
    namespace='ozon',
    serializer=PickleSerializer(),  # TODO: use JsonSerializer
)


def cached_method(
    cache: Cache = _cache,
    key_prefix: str | None = None,
    key_attrs: list[str] | None = None,
    ttl: int = 3600,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator to cache async method results with logging.

    Args:
        cache: Cache instance to use for storing/retrieving values
        key_prefix: Optional string prefix for cache key. If None, uses function name.
        key_attrs: Optional list of attribute paths to include in cache key.
            Uses attrgetter to retrieve nested attributes (e.g., ['credentials.client_id']).
            Attributes are retrieved from self and added to the key.
        ttl: Time-to-live in seconds for cached values (default: 3600)

    Returns:
        Decorator function

    Examples:
        # Using key_prefix and key_attrs
        @cached_method(
            cache=_cache,
            key_prefix='postings_report',
            key_attrs=['credentials.client_id'],
            ttl=3600,
        )
        async def generate_and_download_postings_report(self, filter, language='DEFAULT'):
            return expensive_operation(filter, language)

        # Using only key_attrs (function name will be used as prefix)
        @cached_method(
            cache=_cache,
            key_attrs=['credentials.client_id', 'session.id'],
            ttl=3600,
        )
        async def my_method(self, param):
            return expensive_operation(param)
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(self: Any, *args: P.args, **kwargs: P.kwargs) -> R:
            prefix = key_prefix or func.__name__
            try:
                attr_values = []
                if key_attrs:
                    for attr_path in key_attrs:
                        try:
                            # Use attrgetter for nested attributes like 'credentials.client_id'
                            getter = attrgetter(attr_path)
                            value = getter(self)
                            attr_values.append(str(value))
                        except (AttributeError, TypeError) as e:
                            logger.warning(
                                'Failed to get attribute for cache key',
                                function=func.__name__,
                                attr_path=attr_path,
                                error=str(e),
                            )
                            # Use None as fallback to ensure key uniqueness
                            attr_values.append('None')

                # Build suffix from args/kwargs (excluding self)
                # Create a deterministic hash of the arguments
                key_data = {
                    'args': args,
                    'kwargs': dict(sorted(kwargs.items())),
                }
                key_string = json.dumps(key_data, sort_keys=True, default=str)
                key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

                # Build final cache key: prefix:attr1:attr2:function_name:hash
                key_parts = [prefix]
                if attr_values:
                    key_parts.extend(attr_values)
                key_parts.append(func.__name__)
                key_parts.append(key_hash)

                cache_key = ':'.join(key_parts)
            except Exception as e:
                logger.warning(
                    'Failed to build cache key, skipping cache',
                    function=func.__name__,
                    error=str(e),
                )
                return await func(self, *args, **kwargs)

            # Try to get from cache
            try:
                cached_value = await cache.get(cache_key)
                if cached_value:
                    logger.info(
                        'Cache hit',
                        function=func.__name__,
                        cache_key=cache_key,
                        cache_size=len(cached_value)
                        if isinstance(cached_value, bytes)
                        else None,
                    )
                    return cached_value
            except Exception as e:
                logger.warning(
                    'Failed to retrieve from cache, proceeding with function call',
                    function=func.__name__,
                    cache_key=cache_key,
                    error=str(e),
                )

            # Cache miss - call the function
            logger.debug(
                'Cache miss',
                function=func.__name__,
                cache_key=cache_key,
            )
            result = await func(self, *args, **kwargs)

            # Store result in cache
            try:
                await cache.set(cache_key, result, ttl=ttl)
                logger.info(
                    'Cached result',
                    function=func.__name__,
                    cache_key=cache_key,
                    ttl=ttl,
                    cache_size=len(result) if isinstance(result, bytes) else None,
                )
            except Exception as e:
                logger.warning(
                    'Failed to cache result',
                    function=func.__name__,
                    cache_key=cache_key,
                    error=str(e),
                )

            return result

        return wrapper

    return decorator
