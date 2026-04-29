from typing import List, Any
from unittest.mock import patch, AsyncMock, call
import pytest

from project.core.retry import retry


@pytest.fixture()
def f_sleep():
    with patch('asyncio.sleep', return_value=AsyncMock) as m:
        yield m


class FailHelper:
    def __init__(
        self,
        success_after: int,
        exception: Exception
    ):
        self._success_after = success_after
        self.attempt = 0
        self._exception = exception

    async def run(self) -> int:
        self.attempt += 1
        if self.attempt <= self._success_after:
            raise self._exception

        return self.attempt


@pytest.mark.parametrize('attempt, calls', [(
    1,
    [call(0.5)],
), (
    2,
    [call(0.5), call(1)],
), (
    3,
    [call(0.5), call(1), call(2)],
)])
@pytest.mark.asyncio
async def test_should_retry_function_after_fail(
    f_sleep: AsyncMock,
    attempt: int,
    calls: List[Any]
):
    helper = FailHelper(attempt, Exception())

    @retry(max_attempts=4)
    async def fn():
        return await helper.run()

    await fn()
    assert f_sleep.mock_calls == calls
    assert helper.attempt == attempt + 1


@pytest.mark.asyncio
async def test_should_fail(
    f_sleep: AsyncMock,
):
    helper = FailHelper(5, Exception())

    @retry(max_attempts=3)
    async def fn():
        return await helper.run()

    with pytest.raises(Exception):
        await fn()

    assert f_sleep.mock_calls == [
        call(0.5), call(1)
    ]

    assert helper.attempt == 3
