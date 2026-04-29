from collections.abc import AsyncIterator
import contextlib
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from project.core.config import settings
from project.core.models.base import Base


# Create a single engine instance
_engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=getattr(settings, 'DB_ECHO_LOG', False),
    future=True,
)

# Create a single session factory
async_session = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class DatabaseSessionManager:
    def __init__(self, host: str, engine_kwargs: dict[str, Any] | None = None):
        if engine_kwargs is None:
            engine_kwargs = {}
        self._engine = create_async_engine(host, **engine_kwargs)
        self._sessionmaker = async_sessionmaker(autocommit=False, bind=self._engine)

    async def close(self) -> None:
        if self._engine is None:
            raise Exception('DatabaseSessionManager is not initialized')
        await self._engine.dispose()

        self._engine = None
        self._sessionmaker = None

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self._engine is None:
            raise Exception('DatabaseSessionManager is not initialized')

        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise Exception('DatabaseSessionManager is not initialized')

        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    # Used for testing
    async def create_all(self, connection: AsyncConnection):
        """Create all tables."""
        await connection.run_sync(Base.metadata.create_all)

    async def drop_all(self, connection: AsyncConnection):
        """Drop all tables."""
        await connection.run_sync(Base.metadata.drop_all)


# Create a singleton instance
sessionmanager = DatabaseSessionManager(
    settings.SQLALCHEMY_DATABASE_URI, {'echo': settings.DB_ECHO_LOG}
)


async def get_db_session():
    async with sessionmanager.session() as session:
        yield session
