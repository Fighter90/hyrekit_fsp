"""Личный кабинет работодателя: /api/v1/employer/*."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment.vacancy import preview as assessment_preview
from app.auth.models import User
from app.candidates.models import CandidateProfile
from app.candidates.service import fsp_summary, rating, to_card
from app.catalog.data import GRADE_CODES, GRADE_ORDER, SPEC_CODES, category_title
from app.challenges.models import Challenge, ChallengeSubmission
from app.core.database import get_session
from app.core.exceptions import Conflict, NotFound
from app.core.roles import require_employer
from app.employers import service
from app.employers.models import Company, Vacancy
from app.hiring.models import Application, Invitation, Status
from app.hiring.service import application_out, invitation_out, last_invitation_status, unlocked_profiles
from app.matching.service import _passes_filters, match_vacancy, norm, required_stack, visible_profiles

router = APIRouter(prefix='/employer', tags=['employer'])

Grade = Literal['intern', 'junior', 'middle', 'senior', 'lead']


async def current_company(
    user: User = Depends(require_employer), session: AsyncSession = Depends(get_session)
) -> Company:
    return await service.get_or_create_company(session, user)


# ── Компания ─────────────────────────────────────────────────────────────────
class CompanyIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=255)
    industry: str | None = None
    description: str | None = Field(None, max_length=5000)
    website: str | None = Field(None, max_length=255)
    contact_email: str | None = Field(None, max_length=255)
    contact_phone: str | None = Field(None, max_length=32)
    city: str | None = Field(None, max_length=100)


@router.get('/company', summary='Профиль компании')
async def get_company(company: Company = Depends(current_company)) -> dict:
    return service.company_out(company)


@router.put('/company', summary='Обновить профиль компании')
async def put_company(
    data: CompanyIn, company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> dict:
    for k, v in data.model_dump().items():
        setattr(company, k, v)
    await session.flush()
    return service.company_out(company)


# ── Вакансии / потребности ───────────────────────────────────────────────────
class VacancyIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=10, max_length=10000)
    team_description: str | None = Field(None, max_length=5000)
    specialization: str
    grade_min: Grade
    grade_max: Grade
    stack: list[str] = Field(default_factory=list, max_length=40)
    salary_from: int = Field(ge=1, le=10_000_000, description='Обязательно, ₽')
    salary_to: int = Field(ge=1, le=10_000_000, description='Обязательно, ₽')
    work_format: Literal['office', 'hybrid', 'remote'] = 'hybrid'
    city: str | None = Field(None, max_length=100)
    is_published: bool = False

    @model_validator(mode='after')
    def _check(self) -> VacancyIn:
        if self.specialization not in SPEC_CODES:
            raise ValueError('Неизвестная специализация')
        if GRADE_ORDER[self.grade_min] > GRADE_ORDER[self.grade_max]:
            raise ValueError('grade_min не может быть выше grade_max')
        if self.salary_from > self.salary_to:
            raise ValueError('salary_from не может быть больше salary_to')
        return self


@router.get('/vacancies', summary='Мои потребности и вакансии')
async def list_vacancies(
    company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = list(
        (
            await session.execute(
                select(Vacancy).where(Vacancy.company_id == company.id).order_by(Vacancy.created_at.desc())
            )
        ).scalars()
    )
    counts = await service.applications_count(session, [v.id for v in rows])
    return [service.vacancy_out(v, counts.get(v.id, 0)) for v in rows]


@router.post('/vacancies', status_code=201, summary='Создать потребность')
async def create_vacancy(
    data: VacancyIn, company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> dict:
    v = Vacancy(company_id=company.id, **data.model_dump())
    session.add(v)
    await session.flush()
    await session.refresh(v)
    return service.vacancy_out(v)


@router.get('/vacancies/{vacancy_id}', summary='Потребность')
async def get_vacancy(
    vacancy_id: UUID, company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> dict:
    v = await service.get_own_vacancy(session, company, vacancy_id)
    counts = await service.applications_count(session, [v.id])
    return service.vacancy_out(v, counts.get(v.id, 0))


@router.put('/vacancies/{vacancy_id}', summary='Изменить потребность')
async def update_vacancy(
    vacancy_id: UUID,
    data: VacancyIn,
    company: Company = Depends(current_company),
    session: AsyncSession = Depends(get_session),
) -> dict:
    v = await service.get_own_vacancy(session, company, vacancy_id)
    for k, val in data.model_dump().items():
        setattr(v, k, val)
    await session.flush()
    await session.refresh(v)
    return service.vacancy_out(v)


@router.delete('/vacancies/{vacancy_id}', status_code=204, summary='Удалить потребность', response_class=Response)
async def delete_vacancy(
    vacancy_id: UUID, company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> Response:
    v = await service.get_own_vacancy(session, company, vacancy_id)
    await session.delete(v)
    return Response(status_code=204)


@router.get('/vacancies/{vacancy_id}/matches', summary='Подборка кандидатов с объяснением')
async def vacancy_matches(
    vacancy_id: UUID,
    grade: str | None = None,
    stack: list[str] = Query(default_factory=list),
    has_fsp: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    company: Company = Depends(current_company),
    session: AsyncSession = Depends(get_session),
) -> dict:
    v = await service.get_own_vacancy(session, company, vacancy_id)
    return await match_vacancy(
        session,
        v,
        grade=grade,
        stack=_split(stack),
        has_fsp=has_fsp,
        limit=limit,
        unlocked=await unlocked_profiles(session, company.id),
        statuses=await last_invitation_status(session, company.id),
    )


@router.get('/vacancies/{vacancy_id}/assessment', summary='Тест под вакансию: два варианта равной сложности')
async def vacancy_assessment(
    vacancy_id: UUID,
    company: Company = Depends(current_company),
    session: AsyncSession = Depends(get_session),
) -> dict:
    v = await service.get_own_vacancy(session, company, vacancy_id)
    return assessment_preview(v.specialization, v.grade_min, required_stack(v))


def _split(values: list[str]) -> list[str]:
    """stack можно передать повтором параметра или через запятую."""
    return [s.strip() for v in values for s in v.split(',') if s.strip()]


# ── Банк кандидатов ──────────────────────────────────────────────────────────
@router.get('/candidates', summary='Поиск по банку кандидатов')
async def search_candidates(
    specialization: str | None = None,
    grade: str | None = None,
    category: str | None = None,
    stack: list[str] = Query(default_factory=list),
    has_fsp: bool | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    company: Company = Depends(current_company),
    session: AsyncSession = Depends(get_session),
) -> dict:
    pool = await visible_profiles(session, specialization)
    if category:
        pool = [p for p in pool if p.category == category]
    pool = [p for p in pool if _passes_filters(p, grade, _split(stack), has_fsp)]
    if q:
        ql = q.lower()
        pool = [
            p
            for p in pool
            if ql in (p.headline or '').lower()
            or ql in (p.about or '').lower()
            or any(ql in norm(s) for s in p.stack or [])
        ]
    # внутри категории выше те, у кого сильнее подтверждённый профиль
    pool.sort(key=lambda p: (-GRADE_ORDER.get(p.grade or 'intern', 0), -(rating(p) or 0)))
    unlocked = await unlocked_profiles(session, company.id)
    statuses = await last_invitation_status(session, company.id)
    page = pool[offset : offset + limit]
    return {
        'total': len(pool),
        'items': [to_card(p, contacts_unlocked=p.id in unlocked, invitation_status=statuses.get(p.id)) for p in page],
    }


@router.get('/candidates/{profile_id}', summary='Карточка кандидата')
async def candidate_card(
    profile_id: UUID, company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> dict:
    p = await session.get(CandidateProfile, profile_id)
    unlocked = await unlocked_profiles(session, company.id)
    # профиль без согласия/категории доступен только тем, кому кандидат сам открылся
    if p is None or (not (p.category and p.consent_given_at) and p.id not in unlocked):
        raise NotFound('Кандидат')
    statuses = await last_invitation_status(session, company.id)
    return to_card(p, contacts_unlocked=p.id in unlocked, invitation_status=statuses.get(p.id))


@router.get('/categories', summary='Категории кандидатов и их наполненность')
async def categories(_: Company = Depends(current_company), session: AsyncSession = Depends(get_session)) -> list[dict]:
    stats: dict[str, dict] = {}
    for p in await visible_profiles(session):
        c = stats.setdefault(
            p.category,
            {  # type: ignore[arg-type]
                'category': p.category,
                'title': category_title(p.specialization, p.grade),
                'specialization': p.specialization,
                'grade': p.grade,
                'count': 0,
                'with_fsp': 0,
            },
        )
        c['count'] += 1
        f = fsp_summary(p)
        c['with_fsp'] += bool(f and f['has_history'])
    return sorted(stats.values(), key=lambda c: (c['specialization'], GRADE_CODES.index(c['grade'])))


# ── Приглашения ──────────────────────────────────────────────────────────────
class InvitationIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    candidate_id: UUID
    vacancy_id: UUID | None = None
    title: str = Field(min_length=2, max_length=255)
    message: str = Field(min_length=10, max_length=5000)
    salary_from: int = Field(ge=1, le=10_000_000)
    salary_to: int = Field(ge=1, le=10_000_000)
    contact: str = Field(min_length=3, max_length=255, description='Как связаться: email, телефон, Telegram')

    @model_validator(mode='after')
    def _salary(self) -> InvitationIn:
        if self.salary_from > self.salary_to:
            raise ValueError('salary_from не может быть больше salary_to')
        return self


@router.post('/invitations', status_code=201, summary='Пригласить кандидата')
async def invite(
    data: InvitationIn, company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> dict:
    p = await session.get(CandidateProfile, data.candidate_id)
    if p is None or not (p.category and p.consent_given_at):
        raise NotFound('Кандидат')
    if data.vacancy_id:
        await service.get_own_vacancy(session, company, data.vacancy_id)
    active = (
        (
            await session.execute(
                select(Invitation).where(
                    Invitation.company_id == company.id,
                    Invitation.profile_id == p.id,
                    Invitation.status.in_([Status.SENT, Status.VIEWED]),
                )
            )
        )
        .scalars()
        .first()
    )
    if active:
        raise Conflict('Кандидат ещё не ответил на предыдущее приглашение')
    inv = Invitation(
        company_id=company.id,
        profile_id=p.id,
        status=Status.SENT,
        **data.model_dump(exclude={'candidate_id'}),
    )
    session.add(inv)
    await session.flush()
    await session.refresh(inv)
    return invitation_out(inv, for_employer=True)


@router.get('/invitations', summary='Отправленные приглашения')
async def sent_invitations(
    company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = await session.execute(
        select(Invitation).where(Invitation.company_id == company.id).order_by(Invitation.created_at.desc())
    )
    return [invitation_out(i, for_employer=True) for i in rows.scalars()]


# ── Отклики ──────────────────────────────────────────────────────────────────
@router.get('/applications', summary='Входящие отклики')
async def incoming_applications(
    company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = await session.execute(
        select(Application)
        .join(Vacancy, Vacancy.id == Application.vacancy_id)
        .where(Vacancy.company_id == company.id)
        .order_by(Application.created_at.desc())
    )
    return [application_out(a, for_employer=True) for a in rows.scalars()]


class StatusIn(BaseModel):
    status: Literal['viewed', 'accepted', 'declined']


@router.post('/applications/{app_id}/status', summary='Изменить статус отклика')
async def set_application_status(
    app_id: UUID,
    data: StatusIn,
    company: Company = Depends(current_company),
    session: AsyncSession = Depends(get_session),
) -> dict:
    a = await session.get(Application, app_id)
    if a is None or a.vacancy.company_id != company.id:
        raise NotFound('Отклик')
    a.status = data.status
    await session.flush()
    await session.refresh(a)
    return application_out(a, for_employer=True)


# ── Регулярные задания ───────────────────────────────────────────────────────
class ChallengeIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=5000)
    specialization: str
    due_at: datetime | None = None

    @model_validator(mode='after')
    def _spec(self) -> ChallengeIn:
        if self.specialization not in SPEC_CODES:
            raise ValueError('Неизвестная специализация')
        return self


def _challenge(c: Challenge, n: int) -> dict:
    return {
        'id': c.id,
        'title': c.title,
        'description': c.description,
        'specialization': c.specialization,
        'company_name': c.company.name if c.company else '',
        'due_at': c.due_at,
        'submissions_count': n,
        'created_at': c.created_at,
    }


@router.get('/challenges', summary='Мои короткие задания')
async def list_challenges(
    company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = list(
        (
            await session.execute(
                select(Challenge).where(Challenge.company_id == company.id).order_by(Challenge.created_at.desc())
            )
        ).scalars()
    )
    out = []
    for c in rows:
        n = len(
            list(
                (
                    await session.execute(
                        select(ChallengeSubmission.id).where(ChallengeSubmission.challenge_id == c.id)
                    )
                ).scalars()
            )
        )
        out.append(_challenge(c, n))
    return out


@router.post('/challenges', status_code=201, summary='Создать короткое задание')
async def create_challenge(
    data: ChallengeIn, company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> dict:
    c = Challenge(company_id=company.id, **data.model_dump())
    session.add(c)
    await session.flush()
    await session.refresh(c)
    return _challenge(c, 0)


@router.get('/challenges/{challenge_id}/submissions', summary='Ответы кандидатов')
async def challenge_submissions(
    challenge_id: UUID, company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    c = await session.get(Challenge, challenge_id)
    if c is None or c.company_id != company.id:
        raise NotFound('Задание')
    rows = await session.execute(
        select(ChallengeSubmission, CandidateProfile)
        .join(CandidateProfile, CandidateProfile.id == ChallengeSubmission.profile_id)
        .where(ChallengeSubmission.challenge_id == c.id)
        .order_by(ChallengeSubmission.score.desc().nullslast())
    )
    unlocked = await unlocked_profiles(session, company.id)
    return [
        {
            'id': s.id,
            'answer': s.answer,
            'score': s.score,
            'feedback': s.feedback,
            'created_at': s.created_at,
            'candidate': to_card(p, contacts_unlocked=p.id in unlocked),
        }
        for s, p in rows.all()
    ]
