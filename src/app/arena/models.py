"""ORM-модели Code Arena: раунды, участия, отправки, рейтинг."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDMixin


class ArenaRound(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'arena_rounds'

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    specialization: Mapped[str | None] = mapped_column(String(32), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)  # None — открытый раунд без конца
    duration_minutes: Mapped[int] = mapped_column(Integer)
    is_open: Mapped[bool] = mapped_column(Boolean, default=False)  # таймер у каждого свой
    freeze_minutes: Mapped[int] = mapped_column(Integer, default=0)
    problems: Mapped[list[str]] = mapped_column(JSON, default=list)
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    prize: Mapped[str | None] = mapped_column(String(255))


class ArenaParticipant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'arena_participants'
    __table_args__ = (UniqueConstraint('round_id', 'profile_id', name='uq_arena_participants_round_profile'),)

    round_id: Mapped[UUID] = mapped_column(ForeignKey('arena_rounds.id', ondelete='CASCADE'), index=True)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    solved: Mapped[int] = mapped_column(Integer, default=0)
    penalty: Mapped[int] = mapped_column(Integer, default=0)
    rated_at: Mapped[datetime | None] = mapped_column(DateTime)
    rating_before: Mapped[float | None] = mapped_column(Float)
    rating_after: Mapped[float | None] = mapped_column(Float)


class ArenaSubmission(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'arena_submissions'

    participant_id: Mapped[UUID] = mapped_column(ForeignKey('arena_participants.id', ondelete='CASCADE'), index=True)
    round_id: Mapped[UUID] = mapped_column(ForeignKey('arena_rounds.id', ondelete='CASCADE'), index=True)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'), index=True)
    problem: Mapped[str] = mapped_column(String(48))
    language: Mapped[str] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default='queued', index=True)  # queued | running | done | error
    verdict: Mapped[str | None] = mapped_column(String(8))
    passed: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    time_ms: Mapped[int | None] = mapped_column(Integer)
    memory_kb: Mapped[int | None] = mapped_column(Integer)
    tests: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    message: Mapped[str | None] = mapped_column(Text)
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    signals: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    similar_to: Mapped[UUID | None] = mapped_column(ForeignKey('arena_submissions.id', ondelete='SET NULL'))
    minute: Mapped[int] = mapped_column(Integer, default=0)  # минута от начала участия
    judged_at: Mapped[datetime | None] = mapped_column(DateTime)


class ArenaRating(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'arena_ratings'

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey('candidate_profiles.id', ondelete='CASCADE'), unique=True, index=True
    )
    rating: Mapped[float] = mapped_column(Float)
    rd: Mapped[float] = mapped_column(Float)
    volatility: Mapped[float] = mapped_column(Float)
    rounds: Mapped[int] = mapped_column(Integer, default=0)
    solved: Mapped[int] = mapped_column(Integer, default=0)
    last_round_at: Mapped[datetime | None] = mapped_column(DateTime)
    history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
