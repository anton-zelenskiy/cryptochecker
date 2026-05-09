from __future__ import annotations

import structlog
from celery import Task
from celery.signals import worker_process_shutdown, worker_shutdown
from redis import Redis

from project.core.config import settings

logger = structlog.get_logger(__name__)

_redis_sync: Redis | None = None
_owned_locks_by_id: dict[int, object] = {}


def _release_owned_locks_on_shutdown(**_kwargs) -> None:
    # Best-effort cleanup for graceful worker shutdown.
    # Note: cannot help with SIGKILL; rely on Redis lock TTL in that case.
    locks = list(_owned_locks_by_id.values())
    if not locks:
        return

    released = 0
    failed = 0
    for lock in locks:
        try:
            # redis-py Lock exposes owned()/release(); owned() may raise if redis is down.
            if getattr(lock, "owned")():
                getattr(lock, "release")()
                released += 1
        except Exception:
            failed += 1

    _owned_locks_by_id.clear()
    logger.info(
        "celery exclusive locks cleanup on shutdown",
        released=released,
        failed=failed,
    )


worker_shutdown.connect(_release_owned_locks_on_shutdown)
worker_process_shutdown.connect(_release_owned_locks_on_shutdown)


def _get_redis_sync() -> Redis:
    global _redis_sync
    if _redis_sync is None:
        _redis_sync = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
        )
    return _redis_sync


def _lock_key_for_task(task_name: str) -> str:
    return f"{settings.CELERY_EXCLUSIVE_TASK_LOCK_PREFIX}:{task_name}"


class ExclusivePerTaskNameRedisTask(Task):
    """At most one running instance per Celery task name; overlapping runs are skipped."""

    abstract = True

    def __call__(self, *args, **kwargs):
        redis = _get_redis_sync()
        lock = redis.lock(
            _lock_key_for_task(self.name),
            timeout=settings.CELERY_EXCLUSIVE_LOCK_TIMEOUT_SEC,
            thread_local=False,
        )
        if not lock.acquire(blocking=False):
            logger.info("celery task skipped: already running", task=self.name)
            return None
        _owned_locks_by_id[id(lock)] = lock
        try:
            return super().__call__(*args, **kwargs)
        finally:
            _owned_locks_by_id.pop(id(lock), None)
            try:
                lock.release()
                logger.info("celery task lock released", task=self.name)
            except Exception:
                logger.error("celery task lock release failed", task=self.name)
