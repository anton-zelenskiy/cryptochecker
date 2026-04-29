from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func


class CustomBase:
    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:  # noqa: N805
        return cls.__name__.lower()

    # Add created_at and updated_at to all models
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


Base = declarative_base(cls=CustomBase)
