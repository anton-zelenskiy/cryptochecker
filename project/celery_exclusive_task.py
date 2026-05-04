from __future__ import annotations

import structlog
from celery import Task
from redis import Redis

from project.core.config import settings

logger = structlog.get_logger(__name__)

_worker_redis: Redis | None = None


def _get_worker_redis() -> Redis:
    global _worker_redis
    if _worker_redis is None:
        _worker_redis = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
        )
    return _worker_redis


def _lock_key_for_task(task_name: str) -> str:
    return f"{settings.CELERY_EXCLUSIVE_TASK_LOCK_PREFIX}:{task_name}"


class ExclusivePerTaskNameRedisTask(Task):
    """At most one running instance per Celery task name; overlapping runs are skipped."""

    abstract = True

    def __call__(self, *args, **kwargs):
        client = _get_worker_redis()
        lock = client.lock(
            _lock_key_for_task(self.name),
            timeout=settings.CELERY_EXCLUSIVE_LOCK_TIMEOUT_SEC,
            thread_local=False,
        )
        if not lock.acquire(blocking=False):
            logger.info("celery_task_skipped_already_running", task=self.name)
            return None
        try:
            return super().__call__(*args, **kwargs)
        finally:
            try:
                lock.release()
            except Exception:
                pass
