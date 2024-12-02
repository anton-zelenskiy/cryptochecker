import functools
from typing import Callable
import structlog

logger = structlog.get_logger(__name__)


def error_handler(func: Callable):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f'Error occured: {str(e)}')
    return wrapper
