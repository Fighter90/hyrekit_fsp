"""Pydantic-схемы кабинета кандидата (контракт: docs/spec/api.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.catalog.data import GRADE_CODES, INDUSTRY_CODES, SPEC_CODES

Grade = Literal['intern', 'junior', 'middle', 'senior', 'lead']
WorkFormat = Literal['office', 'hybrid', 'remote']


class Privacy(BaseModel):
    show_full_name: bool = False
    show_city: bool = True
    show_fsp: bool = True
    show_salary: bool = True


class FspAchievement(BaseModel):
    event: str
    discipline: str
    level: str
    place: int | None
    year: int
    role: str | None = None
    relevant_to: list[str] = []


class FspSummary(BaseModel):
    fsp_id: str
    athlete_name: str | None
    achievements: list[FspAchievement]
    score: int
    has_history: bool


class CandidateProfileOut(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str | None
    city: str | None
    phone: str | None
    telegram: str | None
    contact_email: str | None
    headline: str | None
    about: str | None
    industry: str | None
    specialization: str | None
    declared_grade: Grade | None
    grade: Grade | None
    category: str | None
    category_title: str | None
    stack: list[str]
    roles: list[str]
    soft_skills: list[str]
    experience_years: float | None
    salary_from: int | None
    salary_to: int | None
    work_format: WorkFormat | None
    test_score: float | None
    rating: float | None
    grade_changed_at: datetime | None
    next_grade_change_at: datetime | None
    fsp_id: str | None
    fsp: FspSummary | None
    privacy: Privacy
    consent_given_at: datetime | None
    is_visible: bool
    is_guest: bool = False
    completeness: int
    created_at: datetime
    updated_at: datetime


class _Salary(BaseModel):
    salary_from: int | None = Field(None, ge=0, le=10_000_000)
    salary_to: int | None = Field(None, ge=0, le=10_000_000)

    @model_validator(mode='after')
    def _range(self) -> _Salary:
        if self.salary_from is not None and self.salary_to is not None and self.salary_from > self.salary_to:
            raise ValueError('salary_from не может быть больше salary_to')
        return self


class CandidateProfileUpdate(_Salary):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=32)
    telegram: str | None = Field(None, max_length=64)
    contact_email: str | None = Field(None, max_length=255)
    headline: str | None = Field(None, max_length=255)
    about: str | None = Field(None, max_length=5000)
    industry: str | None = None
    stack: list[str] | None = Field(None, max_length=50)
    roles: list[str] | None = Field(None, max_length=20)
    soft_skills: list[str] | None = Field(None, max_length=20)
    experience_years: float | None = Field(None, ge=0, le=60)
    work_format: WorkFormat | None = None

    @model_validator(mode='after')
    def _codes(self) -> CandidateProfileUpdate:
        if self.industry is not None and self.industry not in INDUSTRY_CODES:
            raise ValueError('Неизвестная отрасль')
        return self


class CandidateSettingsUpdate(BaseModel):
    privacy: dict[str, bool] | None = None
    consent: bool | None = None
    fsp_id: str | None = Field(None, max_length=32)


class ResumeParseResult(BaseModel):
    fields: dict
    source: Literal['gigachat', 'rules']
    text_length: int


class SurveyRequest(BaseModel):
    industry: str
    specialization: str
    experience_years: float = Field(ge=0, le=60)
    stack: list[str] = Field(default_factory=list, max_length=50)
    declared_grade: Grade

    @model_validator(mode='after')
    def _codes(self) -> SurveyRequest:
        if self.industry not in INDUSTRY_CODES:
            raise ValueError('Неизвестная отрасль')
        if self.specialization not in SPEC_CODES:
            raise ValueError('Неизвестная специализация')
        if self.declared_grade not in GRADE_CODES:
            raise ValueError('Неизвестный грейд')
        return self
