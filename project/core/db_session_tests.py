import pytest

pytest.skip(
    "DB session integration test requires a running test Postgres/TimescaleDB; "
    "enable in CI with docker service if needed.",
    allow_module_level=True,
)
