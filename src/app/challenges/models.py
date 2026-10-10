"""ORM-модели регулярных коротких заданий."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDMixin
from app.employers.models import Company


class Challenge(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'challenges'

    company_id: Mapped[UUID] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(32), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)

    company: Mapped[Company] = relationship(lazy='joined')


class ChallengeSubmission(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'challenge_submissions'

    challenge_id: Mapped[UUID] = mapped_column(ForeignKey('challenges.id', ondelete='CASCADE'), index=True)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'), index=True)
    answer: Mapped[str] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    feedback: Mapped[str | None] = mapped_column(Text)
