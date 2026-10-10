"""Личный кабинет кандидата: /api/v1/candidate/*."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment import service as assessment
from app.auth.models import User
from app.candidates import service
from app.candidates.models import CandidateProfile
from app.candidates.pdf import render_profile_pdf
from app.candidates.resume_parser import parse_resume_text
from app.candidates.schemas import (
    CandidateProfileOut,
    CandidateProfileUpdate,
    CandidateSettingsUpdate,
    ResumeParseResult,
    SurveyRequest,
)
from app.challenges.models import Challenge, ChallengeSubmission
from app.challenges.service import evaluate
from app.core.config import get_settings
from app.core.database import get_session
from app.core.exceptions import BadRequest, Conflict, NotFound
from app.core.roles import require_candidate
from app.employers.models import Vacancy
from app.employers.service import applications_count, vacancy_out
from app.fsp.provider import FSP_ID_RE, get_provider
from app.hiring.models import Application, Invitation, Status
from app.hiring.service import application_out, invitation_out
from app.ml.parser import detect_file_format, extract_text_from_docx, extract_text_from_pdf

router = APIRouter(prefix='/candidate', tags=['candidate'])


async def current_profile(
    user: User = Depends(require_candidate), session: AsyncSession = Depends(get_session)
) -> CandidateProfile:
    return await service.get_or_create_profile(session, user)


# ── Профиль ──────────────────────────────────────────────────────────────────
@router.get('/profile', response_model=CandidateProfileOut, summary='Свой профиль')
async def get_profile(profile: CandidateProfile = Depends(current_profile)) -> dict:
    return service.to_out(profile)


@router.put('/profile', response_model=CandidateProfileOut, summary='Обновить анкету')
async def update_profile(
    data: CandidateProfileUpdate,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    service.touch(profile)
    await session.flush()
    await session.refresh(profile)
    return service.to_out(profile)


@router.post('/profile/resume', response_model=ResumeParseResult, summary='Загрузить PDF/DOCX и распознать поля')
async def upload_resume(
    file: UploadFile,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict:
    content = await file.read()
    if len(content) > get_settings().max_file_size_bytes:
        raise BadRequest('Файл больше допустимого размера')
    fmt = detect_file_format(content)
    if fmt == 'pdf':
        text = extract_text_from_pdf(content)
    elif fmt == 'docx':
        text = extract_text_from_docx(content)
    else:
        raise BadRequest('Поддерживаются PDF и DOCX')
    if not text.strip():
        raise BadRequest('Не удалось извлечь текст из файла')
    fields, source = await parse_resume_text(text)
    # Заполняем только пустые поля: ручной ввод кандидата приоритетнее
    for key, value in fields.items():
        if key in ('specialization', 'declared_grade'):
            continue
        current = getattr(profile, key, None)
        if current in (None, '', []):
            setattr(profile, key, value)
    profile.resume_text = text[:20000]
    service.touch(profile)
    await session.flush()
    return {'fields': fields, 'source': source, 'text_length': len(text)}


@router.get('/profile/pdf', summary='Стандартизированный PDF-профиль', response_class=Response)
async def profile_pdf(profile: CandidateProfile = Depends(current_profile)) -> Response:
    pdf = render_profile_pdf(service.to_out(profile))
    return Response(
        pdf, media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="hyrekit-profile.pdf"'}
    )


@router.put('/settings', response_model=CandidateProfileOut, summary='Приватность, согласие, ФСП ID')
async def update_settings(
    data: CandidateSettingsUpdate,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if data.privacy:
        allowed = {k: bool(v) for k, v in data.privacy.items() if k in service.DEFAULT_PRIVACY}
        profile.privacy = {**service.DEFAULT_PRIVACY, **(profile.privacy or {}), **allowed}
    if data.consent is not None:
        service.set_consent(session, profile, data.consent)
    if 'fsp_id' in data.model_fields_set:
        if data.fsp_id:
            fsp_id = data.fsp_id.strip().upper()
            if not FSP_ID_RE.match(fsp_id):
                raise BadRequest('ФСП ID имеет формат FSP-123456')
            raw = get_provider().fetch(fsp_id)
            if raw is None:
                raise NotFound('Участник ФСП')
            if fsp_id != profile.fsp_id:  # ручной ввод другого ID снимает подтверждение
                profile.fsp_sub = None
            profile.fsp_id, profile.fsp_snapshot = fsp_id, raw
        else:
            profile.fsp_id, profile.fsp_snapshot, profile.fsp_sub = None, None, None
    await session.flush()
    await session.refresh(profile)
    return service.to_out(profile)


@router.get('/consents', summary='Журнал согласий с версиями текста')
async def consents(
    profile: CandidateProfile = Depends(current_profile), session: AsyncSession = Depends(get_session)
) -> dict:
    return {'current_version': service.CONSENT_VERSION, 'items': await service.consent_history(session, profile)}


@router.get('/fsp', summary='Достижения ФСП по привязанному ID')
async def get_fsp(profile: CandidateProfile = Depends(current_profile)) -> dict | None:
    return service.fsp_summary(profile)


# ── Опрос и тест ─────────────────────────────────────────────────────────────
@router.post('/assessment/survey', response_model=CandidateProfileOut, summary='Опрос: отрасль, специализация, грейд')
async def survey(
    data: SurveyRequest,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if profile.specialization and profile.specialization != data.specialization and profile.grade:
        # смена специализации обнуляет категорию — её нужно подтвердить заново
        profile.grade = profile.category = None
        profile.test_score = profile.ability = None
        profile.grade_changed_at = None
    profile.industry = data.industry
    profile.specialization = data.specialization
    profile.experience_years = data.experience_years
    profile.declared_grade = data.declared_grade
    if data.stack:
        profile.stack = list(dict.fromkeys([*(profile.stack or []), *data.stack]))
    service.touch(profile)
    await session.flush()
    await session.refresh(profile)
    return service.to_out(profile)


@router.get('/assessment/eligibility', summary='Доступные для теста грейды')
async def get_eligibility(profile: CandidateProfile = Depends(current_profile)) -> dict:
    return assessment.eligibility(profile)


class StartRequest(BaseModel):
    grade: str


class AnswerRequest(BaseModel):
    item_id: str
    answer: Any = Field(description='Индекс варианта, список индексов или число')


@router.post('/assessment/start', summary='Начать тест на грейд')
async def start_attempt(
    data: StartRequest,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return assessment.view(await assessment.start(session, profile, data.grade))


@router.get('/assessment/current', summary='Незавершённая попытка, если есть')
async def current_attempt(
    profile: CandidateProfile = Depends(current_profile), session: AsyncSession = Depends(get_session)
) -> dict | None:
    attempt = await assessment.active_attempt(session, profile)
    return assessment.view(attempt) if attempt else None


@router.post('/assessment/{attempt_id}/answer', summary='Сохранить ответ')
async def answer(
    attempt_id: UUID,
    data: AnswerRequest,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict:
    attempt = await assessment.get_attempt(session, profile, attempt_id)
    assessment.save_answer(attempt, data.item_id, data.answer)
    await session.flush()
    return {'saved': True}


@router.post('/assessment/{attempt_id}/finish', summary='Завершить тест и получить результат')
async def finish(
    attempt_id: UUID,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict:
    attempt = await assessment.get_attempt(session, profile, attempt_id)
    return assessment.result(await assessment.finish(session, profile, attempt))


@router.get('/assessment/history', summary='История попыток')
async def attempts_history(
    profile: CandidateProfile = Depends(current_profile), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    return [assessment.result(a) for a in await assessment.history(session, profile)]


# ── Приглашения ──────────────────────────────────────────────────────────────
async def _own_invitation(session: AsyncSession, profile: CandidateProfile, inv_id: UUID) -> Invitation:
    inv = await session.get(Invitation, inv_id)
    if inv is None or inv.profile_id != profile.id:
        raise NotFound('Приглашение')
    return inv


@router.get('/invitations', summary='Мои приглашения')
async def my_invitations(
    profile: CandidateProfile = Depends(current_profile), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = await session.execute(
        select(Invitation).where(Invitation.profile_id == profile.id).order_by(Invitation.created_at.desc())
    )
    return [invitation_out(i, for_employer=False) for i in rows.scalars()]


@router.post('/invitations/{inv_id}/{action}', summary='Просмотреть / принять / отклонить приглашение')
async def invitation_action(
    inv_id: UUID,
    action: str,
    body: dict | None = None,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict:
    inv = await _own_invitation(session, profile, inv_id)
    if action == 'view':
        if inv.status == Status.SENT:
            inv.status = Status.VIEWED
    elif action in ('accept', 'decline'):
        if inv.status in (Status.ACCEPTED, Status.DECLINED):
            raise Conflict('По приглашению уже принято решение')
        inv.status = Status.ACCEPTED if action == 'accept' else Status.DECLINED
        if action == 'decline' and body:
            inv.decline_reason = str(body.get('reason') or '')[:1000] or None
        service.touch(profile)
    else:
        raise NotFound('Действие')
    await session.flush()
    await session.refresh(inv)
    return invitation_out(inv, for_employer=False)


# ── Вакансии и отклики ───────────────────────────────────────────────────────
@router.get('/vacancies', summary='Опубликованные вакансии')
async def vacancies(
    specialization: str | None = None,
    grade: str | None = None,
    q: str | None = Query(None, max_length=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_candidate),
) -> list[dict]:
    from app.catalog.data import GRADE_ORDER

    stmt = select(Vacancy).where(Vacancy.is_published.is_(True)).order_by(Vacancy.created_at.desc())
    if specialization:
        stmt = stmt.where(Vacancy.specialization == specialization)
    items = list((await session.execute(stmt)).scalars())
    if grade in GRADE_ORDER:
        g = GRADE_ORDER[grade]
        items = [v for v in items if GRADE_ORDER[v.grade_min] <= g <= GRADE_ORDER[v.grade_max]]
    if q:
        ql = q.lower()
        items = [
            v
            for v in items
            if ql in v.title.lower() or ql in v.description.lower() or any(ql in s.lower() for s in v.stack or [])
        ]
    counts = await applications_count(session, [v.id for v in items])
    return [vacancy_out(v, counts.get(v.id, 0)) for v in items]


class ApplyRequest(BaseModel):
    message: str | None = Field(None, max_length=3000)


@router.post('/vacancies/{vacancy_id}/apply', summary='Откликнуться на вакансию')
async def apply(
    vacancy_id: UUID,
    data: ApplyRequest,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict:
    v = await session.get(Vacancy, vacancy_id)
    if v is None or not v.is_published:
        raise NotFound('Вакансия')
    exists = (
        await session.execute(
            select(Application).where(Application.vacancy_id == v.id, Application.profile_id == profile.id)
        )
    ).scalar_one_or_none()
    if exists:
        raise Conflict('Вы уже откликнулись на эту вакансию')
    app_ = Application(vacancy_id=v.id, profile_id=profile.id, message=data.message, status=Status.SENT)
    session.add(app_)
    service.touch(profile)
    await session.flush()
    await session.refresh(app_)
    return application_out(app_, for_employer=False)


@router.get('/applications', summary='Мои отклики')
async def my_applications(
    profile: CandidateProfile = Depends(current_profile), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = await session.execute(
        select(Application).where(Application.profile_id == profile.id).order_by(Application.created_at.desc())
    )
    return [application_out(a, for_employer=False) for a in rows.scalars()]


# ── Регулярные задания ───────────────────────────────────────────────────────
def _challenge_out(c: Challenge, submitted: bool) -> dict:
    return {
        'id': c.id,
        'title': c.title,
        'description': c.description,
        'specialization': c.specialization,
        'company_name': c.company.name if c.company else '',
        'due_at': c.due_at,
        'submitted': submitted,
    }


@router.get('/challenges', summary='Короткие задания по моей специализации')
async def my_challenges(
    profile: CandidateProfile = Depends(current_profile), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    if not profile.specialization:
        return []
    rows = await session.execute(
        select(Challenge)
        .where(Challenge.specialization == profile.specialization)
        .order_by(Challenge.created_at.desc())
    )
    done = set(
        (
            await session.execute(
                select(ChallengeSubmission.challenge_id).where(ChallengeSubmission.profile_id == profile.id)
            )
        ).scalars()
    )
    return [_challenge_out(c, c.id in done) for c in rows.scalars()]


class SubmitRequest(BaseModel):
    answer: str = Field(min_length=10, max_length=10000)


@router.post('/challenges/{challenge_id}/submit', summary='Отправить решение или подход')
async def submit_challenge(
    challenge_id: UUID,
    data: SubmitRequest,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ch = await session.get(Challenge, challenge_id)
    if ch is None or ch.specialization != profile.specialization:
        raise NotFound('Задание')
    exists = (
        await session.execute(
            select(ChallengeSubmission).where(
                ChallengeSubmission.challenge_id == ch.id, ChallengeSubmission.profile_id == profile.id
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise Conflict('Решение уже отправлено')
    score, feedback = await evaluate(f'{ch.title}\n{ch.description}', data.answer)
    sub = ChallengeSubmission(
        challenge_id=ch.id, profile_id=profile.id, answer=data.answer, score=score, feedback=feedback
    )
    session.add(sub)
    service.touch(profile)
    await session.flush()
    await session.refresh(sub)
    return {
        'id': sub.id,
        'challenge_id': ch.id,
        'answer': sub.answer,
        'score': sub.score,
        'feedback': sub.feedback,
        'created_at': sub.created_at,
    }
