"""ORM-модель профиля кандидата."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDMixin

DEFAULT_PRIVACY: dict[str, bool] = {
    'show_full_name': False,
    'show_city': True,
    'show_fsp': True,
    'show_salary': True,
}


class CandidateProfile(UUIDMixin, TimestampMixin, Base):
    """Анкета кандидата, результат опроса и подтверждённая категория."""

    __tablename__ = 'candidate_profiles'

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(32))
    telegram: Mapped[str | None] = mapped_column(String(64))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    headline: Mapped[str | None] = mapped_column(String(255))
    about: Mapped[str | None] = mapped_column(Text)

    # Опрос
    industry: Mapped[str | None] = mapped_column(String(32))
    specialization: Mapped[str | None] = mapped_column(String(32), index=True)
    declared_grade: Mapped[str | None] = mapped_column(String(16))
    experience_years: Mapped[float | None] = mapped_column(Float)
    stack: Mapped[list[str]] = mapped_column(JSON, default=list)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    soft_skills: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Условия
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    work_format: Mapped[str | None] = mapped_column(String(16))

    # Подтверждённая категория (по итогам теста)
    grade: Mapped[str | None] = mapped_column(String(16), index=True)
    category: Mapped[str | None] = mapped_column(String(48), index=True)
    test_score: Mapped[float | None] = mapped_column(Float)
    ability: Mapped[float | None] = mapped_column(Float)
    grade_changed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime)

    # ФСП и приватность
    fsp_id: Mapped[str | None] = mapped_column(String(32), index=True)
    fsp_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    privacy: Mapped[dict[str, bool]] = mapped_column(JSON, default=lambda: dict(DEFAULT_PRIVACY))
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Источник данных анкеты (форма / распознанное резюме)
    resume_text: Mapped[str | None] = mapped_column(Text)


class ConsentEvent(UUIDMixin, TimestampMixin, Base):
    """Журнал согласий кандидата: каждая выдача и отзыв с версией текста (152-ФЗ, ст. 9)."""

    __tablename__ = 'consent_events'

    profile_id: Mapped[UUID] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(32), default='publication')
    version: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(16))  # given | revoked
