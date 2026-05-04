from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from celery import Celery

from project.celery_exclusive_task import ExclusivePerTaskNameRedisTask


@pytest.fixture
def mock_redis_lock():
    lock = MagicMock()
    lock.acquire.return_value = True
    return lock


@pytest.fixture
def mock_redis_client(mock_redis_lock):
    client = MagicMock()
    client.lock.return_value = mock_redis_lock
    return client


def test_exclusive_task_acquires_releases_lock(mock_redis_client, mock_redis_lock):
    app = Celery("test_exclusive")
    app.Task = ExclusivePerTaskNameRedisTask

    @app.task(name="test.add")
    def add(x: int, y: int) -> int:
        return x + y

    with patch(
        "project.celery_exclusive_task._get_worker_redis",
        return_value=mock_redis_client,
    ):
        result = add.apply(args=(2, 3))

    assert result.successful()
    assert result.result == 5
    mock_redis_client.lock.assert_called_once()
    mock_redis_lock.acquire.assert_called_once_with(blocking=False)
    mock_redis_lock.release.assert_called_once()


def test_exclusive_task_releases_lock_on_error(mock_redis_client, mock_redis_lock):
    app = Celery("test_exclusive_err")
    app.Task = ExclusivePerTaskNameRedisTask

    @app.task(name="test.boom")
    def boom() -> None:
        raise ValueError("x")

    with patch(
        "project.celery_exclusive_task._get_worker_redis",
        return_value=mock_redis_client,
    ):
        result = boom.apply()

    assert not result.successful()
    mock_redis_lock.release.assert_called_once()


def test_skips_when_same_task_already_running(mock_redis_client, mock_redis_lock):
    mock_redis_lock.acquire.return_value = False
    ran: list[int] = []

    app = Celery("test_skip")
    app.Task = ExclusivePerTaskNameRedisTask

    @app.task(name="test.work")
    def work() -> str:
        ran.append(1)
        return "done"

    with patch(
        "project.celery_exclusive_task._get_worker_redis",
        return_value=mock_redis_client,
    ):
        result = work.apply()

    assert result.successful()
    assert result.result is None
    assert ran == []
    mock_redis_lock.release.assert_not_called()
