"""Code Arena: /api/v1/arena/*."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.arena import judge, problems, service
from app.arena.models import ArenaParticipant, ArenaRating, ArenaRound, ArenaSubmission
from app.auth.models import User, UserRole
from app.candidates.models import DEFAULT_PRIVACY, CandidateProfile
from app.candidates.service import fsp_summary, get_or_create_profile, to_card, utcnow
from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.exceptions import Forbidden, NotFound
from app.core.limiter import limiter, user_or_ip
from app.core.roles import require_candidate, require_employer
from app.employers.models import Company
from app.employers.service import get_or_create_company
from app.hiring.service import last_invitation_status, unlocked_profiles

router = APIRouter(prefix='/arena', tags=['arena'])

Language = Literal['python', 'javascript']


async def current_profile(
    user: User = Depends(require_candidate), session: AsyncSession = Depends(get_session)
) -> CandidateProfile:
    return await get_or_create_profile(session, user)


async def current_company(
    user: User = Depends(require_employer), session: AsyncSession = Depends(get_session)
) -> Company:
    return await get_or_create_company(session, user)


async def _viewer(user: User, session: AsyncSession) -> tuple[CandidateProfile | None, Company | None]:
    if user.role == UserRole.CANDIDATE:
        return await get_or_create_profile(session, user), None
    if user.role == UserRole.EMPLOYER:
        return None, await get_or_create_company(session, user)
    raise Forbidden('Раздел доступен кандидатам и работодателям')


async def _sponsors(session: AsyncSession, rounds: list[ArenaRound]) -> dict[UUID, str]:
    ids = {r.company_id for r in rounds if r.company_id}
    if not ids:
        return {}
    rows = await session.execute(select(Company.id, Company.name).where(Company.id.in_(ids)))
    return dict(rows.all())  # type: ignore[arg-type]


async def _counts(session: AsyncSession, round_ids: list[UUID]) -> dict[UUID, int]:
    if not round_ids:
        return {}
    rows = await session.execute(
        select(ArenaParticipant.round_id, func.count())
        .where(ArenaParticipant.round_id.in_(round_ids))
        .group_by(ArenaParticipant.round_id)
    )
    return dict(rows.all())  # type: ignore[arg-type]


# ── Общие ────────────────────────────────────────────────────────────────────
@router.get('/sandbox', summary='Слои песочницы и доступные языки')
async def sandbox_info() -> dict[str, Any]:
    caps = await asyncio.to_thread(judge.capabilities)
    return {
        **caps,
        'max_parallel': judge.MAX_PARALLEL,
        'language_titles': {k: judge.LANGUAGE_TITLES[k] for k in caps['languages']},
        'limits': {
            'time_ms': int(judge.TIME_LIMIT_S * 1000),
            'memory_mb': judge.MEMORY_MB,
            'code_kb': judge.CODE_LIMIT_KB,
        },
    }


@router.get('/problems', summary='Банк задач Arena')
async def problem_bank() -> list[dict[str, Any]]:
    return problems.catalog()


@router.get('/rounds', summary='Раунды: открытый, идущие, будущие и прошедшие')
async def list_rounds(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    profile, company = await _viewer(user, session)
    await service.ensure_open_round(session)
    now = utcnow()
    rounds = list((await session.execute(select(ArenaRound).order_by(ArenaRound.starts_at.desc()).limit(50))).scalars())
    if profile:
        rounds = [
            r
            for r in rounds
            if not r.specialization or not profile.specialization or r.specialization == profile.specialization
        ]
    order = {'running': 0, 'upcoming': 1, 'finished': 2}
    rounds.sort(key=lambda r: (not r.is_open, order[service.round_state(r, now)], r.starts_at))
    sponsors = await _sponsors(session, rounds)
    counts = await _counts(session, [r.id for r in rounds])
    mine: dict[UUID, ArenaParticipant] = {}
    if profile:
        rows = await session.execute(select(ArenaParticipant).where(ArenaParticipant.profile_id == profile.id))
        mine = {p.round_id: p for p in rows.scalars()}
    out = []
    for r in rounds:
        item = service.round_out(
            r, now, participant=mine.get(r.id), sponsor=sponsors.get(r.company_id), participants=counts.get(r.id, 0)
        )  # type: ignore[arg-type]
        item['mine'] = bool(company and r.company_id == company.id)
        out.append(item)
    return out


@router.get('/rounds/{round_id}', summary='Раунд: задачи своего варианта и мои отправки')
async def get_round(
    round_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    profile, company = await _viewer(user, session)
    r = await service.get_round(session, round_id)
    now = utcnow()
    part = await service.get_participant(session, r, profile) if profile else None
    if part:
        await service.finalize_due(session, profile_id=profile.id)  # type: ignore[union-attr]
    sponsors = await _sponsors(session, [r])
    counts = await _counts(session, [r.id])
    out = service.round_out(
        r, now, participant=part, sponsor=sponsors.get(r.company_id), participants=counts.get(r.id, 0)
    )  # type: ignore[arg-type]
    out['mine'] = bool(company and r.company_id == company.id)
    out['tasks'] = []
    out['submissions'] = []
    if part and profile:
        out['tasks'] = [problems.public(service.participant_variant(r, profile.id, c)) for c in r.problems]
        subs = await session.execute(
            select(ArenaSubmission)
            .where(ArenaSubmission.participant_id == part.id)
            .order_by(ArenaSubmission.created_at.desc())
        )
        out['submissions'] = [service.submission_out(s, with_code=True) for s in subs.scalars()]
    out['languages'] = (await asyncio.to_thread(judge.capabilities))['languages']
    return out


@router.get('/rounds/{round_id}/leaderboard', summary='Таблица раунда')
async def leaderboard(
    round_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    profile, company = await _viewer(user, session)
    r = await service.get_round(session, round_id)
    board = await service.leaderboard(
        session, r, viewer_profile_id=profile.id if profile else None, employer=company is not None
    )
    if company:
        statuses = await last_invitation_status(session, company.id)
        for row in board['rows']:
            row['invitation_status'] = statuses.get(row['profile_id'])
    return board


@router.get('/rounds/{round_id}/stream', summary='Изменения таблицы (Server-Sent Events)')
async def stream(
    round_id: UUID,
    request: Request,
    once: bool = Query(False, description='Отдать одно событие и закрыть поток (для проверки)'),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    await _viewer(user, session)
    await service.get_round(session, round_id)

    async def events() -> AsyncIterator[str]:
        last = None
        idle = 0
        for _ in range(900):  # не дольше 30 минут, клиент переподключится
            if await request.is_disconnected():
                return
            stamp = await service.board_stamp(session, round_id)
            await session.commit()
            if stamp != last:
                last = stamp
                yield f'event: board\ndata: {json.dumps({"version": stamp})}\n\n'
                idle = 0
                if once:
                    return
            else:
                idle += 1
                if idle % 8 == 0:
                    yield ': ping\n\n'
            await asyncio.sleep(2)

    return StreamingResponse(
        events(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


@router.get('/rounds/{round_id}/editorial', summary='Разбор задач: эталоны и статистика')
async def editorial(
    round_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    profile, company = await _viewer(user, session)
    r = await service.get_round(session, round_id)
    now = utcnow()
    if profile:
        part = await service.get_participant(session, r, profile)
        over = part is not None and (part.finished_at is not None or now >= part.ends_at)
        if not over and service.round_state(r, now) != 'finished':
            raise Forbidden('Разбор откроется, когда закончится ваше время в раунде')
    elif company and r.company_id != company.id and service.round_state(r, now) != 'finished':
        raise Forbidden('Разбор чужого раунда откроется после его окончания')
    return {'round_id': r.id, 'problems': await service.editorial(session, r, profile.id if profile else None)}


# ── Кандидат ─────────────────────────────────────────────────────────────────
class CodeIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=False)
    problem: str = Field(min_length=1, max_length=48)
    language: Language = 'python'
    code: str = Field(min_length=1, max_length=judge.CODE_LIMIT_KB * 1024)


class SubmitIn(CodeIn):
    signals: dict[str, int] = Field(default_factory=dict)


@router.post('/rounds/{round_id}/join', summary='Участвовать в раунде')
async def join(
    round_id: UUID, profile: CandidateProfile = Depends(current_profile), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    r = await service.get_round(session, round_id)
    p = await service.join(session, r, profile)
    return service.participation_out(p, utcnow())


@router.post('/rounds/{round_id}/run', summary='Запустить на примерах (не засчитывается)')
@limiter.limit('20/minute', key_func=user_or_ip)
async def run(
    request: Request,
    round_id: UUID,
    data: CodeIn,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    r = await service.get_round(session, round_id)
    service.require_active(await service.get_participant(session, r, profile), utcnow())
    await session.commit()
    return await service.run_samples(r, profile, data.problem, data.language, data.code)


@router.post('/rounds/{round_id}/submit', summary='Отправить решение на проверку')
@limiter.limit('10/minute', key_func=user_or_ip)
async def submit(
    request: Request,
    round_id: UUID,
    data: SubmitIn,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    r = await service.get_round(session, round_id)
    sub = await service.submit(session, r, profile, data.problem, data.language, data.code, data.signals)
    p = await session.get(ArenaParticipant, sub.participant_id)
    return {
        'submission': service.submission_out(sub, with_code=True),
        'participation': service.participation_out(p, utcnow()),
    }  # type: ignore[arg-type]


@router.post('/rounds/{round_id}/finish', summary='Завершить участие досрочно и получить рейтинг')
async def finish(
    round_id: UUID, profile: CandidateProfile = Depends(current_profile), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    r = await service.get_round(session, round_id)
    p = await service.get_participant(session, r, profile)
    if p is None:
        raise NotFound('Участие')
    await service.finish(session, p)
    return service.participation_out(p, utcnow())


@router.get('/submissions/{submission_id}', summary='Отправка и её разбор')
async def submission(
    submission_id: UUID,
    profile: CandidateProfile = Depends(current_profile),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    s = await session.get(ArenaSubmission, submission_id)
    if s is None or s.profile_id != profile.id:
        raise NotFound('Отправка')
    return service.submission_out(s, with_code=True)


@router.get('/me', summary='Мой рейтинг Arena и история')
async def me(
    profile: CandidateProfile = Depends(current_profile), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    await service.finalize_due(session, profile_id=profile.id)
    now = utcnow()
    rt = (await session.execute(select(ArenaRating).where(ArenaRating.profile_id == profile.id))).scalars().first()
    rows = await session.execute(
        select(ArenaParticipant, ArenaRound)
        .join(ArenaRound, ArenaRound.id == ArenaParticipant.round_id)
        .where(ArenaParticipant.profile_id == profile.id)
        .order_by(ArenaParticipant.started_at.desc())
    )
    privacy = {**DEFAULT_PRIVACY, **(profile.privacy or {})}
    return {
        'rating': service.rating_out(rt, now),
        'top_percent': await service.percentile(session, rt, profile.specialization) if rt else None,
        'participations': [
            {'round_id': r.id, 'round': r.title, **service.participation_out(p, now)} for p, r in rows.all()
        ],
        'show_arena': bool(privacy.get('show_arena')),
        'display_name': service.display_name(profile),
    }


class ArenaSettingsIn(BaseModel):
    show_arena: bool


@router.put('/me/settings', summary='Показывать имя и решения в Arena')
async def settings(data: ArenaSettingsIn, profile: CandidateProfile = Depends(current_profile)) -> dict[str, Any]:
    profile.privacy = {**DEFAULT_PRIVACY, **(profile.privacy or {}), 'show_arena': data.show_arena}
    return {'show_arena': data.show_arena, 'display_name': service.display_name(profile)}


# ── Работодатель ─────────────────────────────────────────────────────────────
class RoundIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=255)
    description: str | None = Field(None, max_length=4000)
    specialization: str | None = None
    problems: list[str] = Field(min_length=1, max_length=8)
    starts_at: datetime
    duration_minutes: int = Field(60, ge=service.MIN_DURATION, le=service.MAX_DURATION)
    prize: str | None = Field(None, max_length=255)


@router.post('/rounds', status_code=201, summary='Создать раунд работодателя')
async def create_round(
    data: RoundIn, company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    starts = data.starts_at.astimezone(UTC).replace(tzinfo=None) if data.starts_at.tzinfo else data.starts_at
    r = await service.create_round(
        session,
        company_id=company.id,
        title=data.title,
        description=data.description,
        specialization=data.specialization or None,
        problem_codes=data.problems,
        starts_at=starts,
        duration_minutes=data.duration_minutes,
        prize=data.prize,
    )
    out = service.round_out(r, utcnow(), sponsor=company.name)
    out['mine'] = True
    return out


@router.get('/top', summary='Витрина: кандидаты по рейтингу Arena')
async def top(
    specialization: str | None = None,
    grade: str | None = None,
    has_fsp: bool | None = None,
    min_rating: int | None = Query(None, ge=0, le=4000),
    limit: int = Query(50, ge=1, le=200),
    company: Company = Depends(current_company),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await service.finalize_due(session)
    now = utcnow()
    stmt = (
        select(ArenaRating, CandidateProfile)
        .join(CandidateProfile, CandidateProfile.id == ArenaRating.profile_id)
        .where(CandidateProfile.category.is_not(None), CandidateProfile.consent_given_at.is_not(None))
    )
    if specialization:
        stmt = stmt.where(CandidateProfile.specialization == specialization)
    if grade:
        stmt = stmt.where(CandidateProfile.grade == grade)
    rows = (await session.execute(stmt)).all()
    unlocked = await unlocked_profiles(session, company.id)
    statuses = await last_invitation_status(session, company.id)
    items = []
    for rt, prof in rows:
        cur = service.rating_out(rt, now)
        if min_rating and cur['rating'] < min_rating:  # type: ignore[index]
            continue
        fsp = fsp_summary(prof)
        if has_fsp is not None and bool(fsp and fsp['has_history']) != has_fsp:
            continue
        card = to_card(prof, contacts_unlocked=prof.id in unlocked, invitation_status=statuses.get(prof.id))
        if not ({**DEFAULT_PRIVACY, **(prof.privacy or {})}.get('show_arena')) and prof.id not in unlocked:
            card['display_name'] = service.display_name(prof)
        items.append(
            {'candidate': card, 'arena': cur, 'top_percent': await service.percentile(session, rt, prof.specialization)}
        )
    items.sort(key=lambda x: (x['arena']['provisional'], -x['arena']['rating']))
    return {'total': len(items), 'items': items[:limit]}


@router.get('/candidates/{profile_id}', summary='Arena-профиль кандидата: рейтинг, история, решения')
async def candidate_arena(
    profile_id: UUID, company: Company = Depends(current_company), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    prof = await session.get(CandidateProfile, profile_id)
    if prof is None or not prof.consent_given_at:
        raise NotFound('Кандидат')
    now = utcnow()
    rt = (await session.execute(select(ArenaRating).where(ArenaRating.profile_id == prof.id))).scalars().first()
    unlocked = prof.id in await unlocked_profiles(session, company.id)
    show = bool({**DEFAULT_PRIVACY, **(prof.privacy or {})}.get('show_arena')) or unlocked
    solutions: list[dict[str, Any]] = []
    if show:
        rows = await session.execute(
            select(ArenaSubmission, ArenaRound)
            .join(ArenaRound, ArenaRound.id == ArenaSubmission.round_id)
            .where(ArenaSubmission.profile_id == prof.id, ArenaSubmission.verdict == 'OK')
            .order_by(ArenaSubmission.created_at.desc())
            .limit(20)
        )
        solutions = [
            {
                **service.submission_out(s, with_code=True),
                'round': r.title,
                'problem_title': problems.PROBLEMS[s.problem].title,
            }
            for s, r in rows.all()
        ]
    suspicious = (
        await session.execute(
            select(func.count())
            .select_from(ArenaSubmission)
            .where(ArenaSubmission.profile_id == prof.id, ArenaSubmission.similar_to.is_not(None))
        )
    ).scalar_one()
    return {
        'profile_id': prof.id,
        'display_name': prof.full_name if show and prof.full_name else service.display_name(prof),
        'rating': service.rating_out(rt, now),
        'top_percent': await service.percentile(session, rt, prof.specialization) if rt else None,
        'solutions_visible': show,
        'solutions': solutions,
        'suspicious_submissions': suspicious,
    }
