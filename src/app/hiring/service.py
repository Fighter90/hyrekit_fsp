"""Представления приглашений и откликов + правила раскрытия контактов."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.service import to_card
from app.employers.service import vacancy_out
from app.hiring.models import Application, Invitation, Status


async def unlocked_profiles(session: AsyncSession, company_id: UUID) -> set[UUID]:
    """Профили, контакты которых компания видит: приглашение принято или кандидат откликнулся сам."""
    from app.employers.models import Vacancy

    inv = select(Invitation.profile_id).where(Invitation.company_id == company_id, Invitation.status == Status.ACCEPTED)
    app_ = (
        select(Application.profile_id)
        .join(Vacancy, Vacancy.id == Application.vacancy_id)
        .where(Vacancy.company_id == company_id, Application.status != Status.DECLINED)
    )
    ids = set((await session.execute(inv)).scalars()) | set((await session.execute(app_)).scalars())
    return ids


async def last_invitation_status(session: AsyncSession, company_id: UUID) -> dict[UUID, str]:
    rows = await session.execute(
        select(Invitation.profile_id, Invitation.status)
        .where(Invitation.company_id == company_id)
        .order_by(Invitation.created_at)
    )
    return dict(rows.all())  # type: ignore[arg-type]


def invitation_out(inv: Invitation, *, for_employer: bool) -> dict[str, Any]:
    unlocked = inv.status == Status.ACCEPTED
    return {
        'id': inv.id,
        'status': inv.status,
        'company': {
            'id': inv.company.id,
            'name': inv.company.name,
            'industry': inv.company.industry,
            'website': inv.company.website,
        },
        'vacancy_id': inv.vacancy_id,
        'title': inv.title,
        'message': inv.message,
        'salary_from': inv.salary_from,
        'salary_to': inv.salary_to,
        'contact': inv.contact,
        'decline_reason': inv.decline_reason,
        'candidate': to_card(inv.profile, contacts_unlocked=unlocked, invitation_status=inv.status)
        if for_employer
        else None,
        'created_at': inv.created_at,
        'updated_at': inv.updated_at,
    }


def application_out(a: Application, *, for_employer: bool) -> dict[str, Any]:
    return {
        'id': a.id,
        'status': a.status,
        'vacancy': vacancy_out(a.vacancy),
        'message': a.message,
        # отклик — инициатива кандидата, поэтому контакты сразу доступны работодателю
        'candidate': to_card(a.profile, contacts_unlocked=a.status != Status.DECLINED) if for_employer else None,
        'created_at': a.created_at,
        'updated_at': a.updated_at,
    }
