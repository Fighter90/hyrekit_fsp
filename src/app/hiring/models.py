"""ORM-модели приглашения (инициатива работодателя) и отклика (инициатива кандидата)."""

from __future__ import annotations

import enum
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.candidates.models import CandidateProfile
from app.core.database import Base, TimestampMixin, UUIDMixin
from app.employers.models import Company, Vacancy


class Status(enum.StrEnum):
    SENT = 'sent'
    VIEWED = 'viewed'
    ACCEPTED = 'accepted'
    DECLINED = 'declined'


class Invitation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'invitations'

    company_id: Mapped[UUID] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'), index=True)
    vacancy_id: Mapped[UUID | None] = mapped_column(ForeignKey('vacancies.id', ondelete='SET NULL'))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    contact: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default=Status.SENT, index=True)
    decline_reason: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(lazy='joined')
    profile: Mapped[CandidateProfile] = relationship(lazy='joined')


class Application(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'applications'

    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey('vacancies.id', ondelete='CASCADE'), index=True)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'), index=True)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=Status.SENT, index=True)

    vacancy: Mapped[Vacancy] = relationship(lazy='joined')
    profile: Mapped[CandidateProfile] = relationship(lazy='joined')
