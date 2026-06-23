"""SQLAlchemy base model with ULID primary keys and timestamp mixin."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.id import generate_ulid
from app.utils.timezone import shanghai_now


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    time_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=shanghai_now,
        nullable=False,
    )
    time_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=shanghai_now,
        onupdate=shanghai_now,
        nullable=False,
    )
