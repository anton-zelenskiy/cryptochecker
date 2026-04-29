from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase

from project.core.db_session import DatabaseSessionManager, sessionmanager as default_sessionmanager

ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(Generic[ModelType]):
    def __init__(
        self,
        model: type[ModelType],
        sessionmanager: DatabaseSessionManager | None = None,
    ) -> None:
        self._model = model
        self._sessionmanager = sessionmanager or default_sessionmanager

    async def get_by_id(self, id: int) -> ModelType | None:
        async with self._sessionmanager.session() as session:
            stmt = select(self._model).where(self._model.id == id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all(self) -> list[ModelType]:
        async with self._sessionmanager.session() as session:
            stmt = select(self._model)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> ModelType:
        async with self._sessionmanager.session() as session:
            entity = self._model(**kwargs)
            session.add(entity)
            await session.commit()
            await session.refresh(entity)
            return entity

    async def update(self, id: int, **kwargs: Any) -> ModelType | None:
        async with self._sessionmanager.session() as session:
            stmt = select(self._model).where(self._model.id == id)
            result = await session.execute(stmt)
            entity = result.scalar_one_or_none()

            if entity:
                for key, value in kwargs.items():
                    setattr(entity, key, value)
                await session.commit()
                await session.refresh(entity)

            return entity

    async def delete(self, id: int) -> bool:
        async with self._sessionmanager.session() as session:
            stmt = select(self._model).where(self._model.id == id)
            result = await session.execute(stmt)
            entity = result.scalar_one_or_none()

            if entity:
                await session.delete(entity)
                await session.commit()
                return True

            return False
