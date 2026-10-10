"""Компания и вакансии работодателя."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import NotFound
from app.employers.models import Company, Vacancy


async def get_or_create_company(session: AsyncSession, user: User) -> Company:
    company = (await session.execute(select(Company).where(Company.owner_id == user.id))).scalar_one_or_none()
    if company is None:
        company = Company(owner_id=user.id, name=user.full_name or 'Моя компания', contact_email=user.email)
        session.add(company)
        await session.flush()
    return company


def company_out(c: Company) -> dict[str, Any]:
    return {
        'id': c.id,
        'name': c.name,
        'industry': c.industry,
        'description': c.description,
        'website': c.website,
        'contact_email': c.contact_email,
        'contact_phone': c.contact_phone,
        'city': c.city,
    }


def vacancy_out(v: Vacancy, applications_count: int = 0) -> dict[str, Any]:
    return {
        'id': v.id,
        'company': {'id': v.company.id, 'name': v.company.name} if v.company else None,
        'title': v.title,
        'description': v.description,
        'team_description': v.team_description,
        'specialization': v.specialization,
        'grade_min': v.grade_min,
        'grade_max': v.grade_max,
        'stack': v.stack or [],
        'salary_from': v.salary_from,
        'salary_to': v.salary_to,
        'work_format': v.work_format,
        'city': v.city,
        'is_published': v.is_published,
        'applications_count': applications_count,
        'created_at': v.created_at,
        'updated_at': v.updated_at,
    }


async def get_own_vacancy(session: AsyncSession, company: Company, vacancy_id: UUID) -> Vacancy:
    v = await session.get(Vacancy, vacancy_id)
    if v is None or v.company_id != company.id:
        raise NotFound('Вакансия')
    return v


async def applications_count(session: AsyncSession, vacancy_ids: list[UUID]) -> dict[UUID, int]:
    from app.hiring.models import Application

    if not vacancy_ids:
        return {}
    rows = await session.execute(
        select(Application.vacancy_id, func.count())
        .where(Application.vacancy_id.in_(vacancy_ids))
        .group_by(Application.vacancy_id)
    )
    return dict(rows.all())  # type: ignore[arg-type]
