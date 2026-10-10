"""ORM-модели компании и вакансии (потребности)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDMixin


class Company(UUIDMixin, TimestampMixin, Base):
    __tablename__ = 'companies'

    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    city: Mapped[str | None] = mapped_column(String(100))


class Vacancy(UUIDMixin, TimestampMixin, Base):
    """Потребность работодателя. Опубликованная потребность видна кандидатам как вакансия."""

    __tablename__ = 'vacancies'

    company_id: Mapped[UUID] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    team_description: Mapped[str | None] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(32), index=True)
    grade_min: Mapped[str] = mapped_column(String(16))
    grade_max: Mapped[str] = mapped_column(String(16))
    stack: Mapped[list[str]] = mapped_column(JSON, default=list)
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    work_format: Mapped[str] = mapped_column(String(16), default='hybrid')
    city: Mapped[str | None] = mapped_column(String(100))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    company: Mapped[Company] = relationship(lazy='joined')
