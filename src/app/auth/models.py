"""SQLAlchemy-модель пользователя."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDMixin


class UserRole(enum.StrEnum):
    """Роль пользователя: личный кабинет кандидата или работодателя."""

    CANDIDATE = 'candidate'
    EMPLOYER = 'employer'


class User(UUIDMixin, TimestampMixin, Base):
    """Модель пользователя."""

    __tablename__ = 'users'

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name='user_role', native_enum=False),
        default=UserRole.CANDIDATE,
        server_default='candidate',
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    scheduled_deletion: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
    )
