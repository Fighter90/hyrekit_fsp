"""ORM-модель попытки тестирования."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDMixin


class AssessmentAttempt(UUIDMixin, TimestampMixin, Base):
    """Попытка теста на грейд. План заданий хранится зёрнами — варианты воспроизводимы."""

    __tablename__ = 'assessment_attempts'

    profile_id: Mapped[UUID] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'), index=True)
    specialization: Mapped[str] = mapped_column(String(32))
    grade: Mapped[str] = mapped_column(String(16))
    plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    deadline_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    score: Mapped[float | None] = mapped_column(Float)
    ability: Mapped[float | None] = mapped_column(Float)
    correct: Mapped[int | None] = mapped_column(Integer)
    total: Mapped[int | None] = mapped_column(Integer)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    assigned_grade: Mapped[str | None] = mapped_column(String(16))
    suggestion: Mapped[str | None] = mapped_column(String(16))
    by_topic: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
