"""Логика Code Arena без HTTP: раунды, участие, проверка, таблица, рейтинг."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.arena import feedback, judge, problems, rating, similarity
from app.arena.models import ArenaParticipant, ArenaRating, ArenaRound, ArenaSubmission
from app.candidates.models import DEFAULT_PRIVACY, CandidateProfile
from app.candidates.service import public_alias, utcnow
from app.catalog.data import SPEC_BY_CODE, category_title
from app.core.exceptions import BadRequest, Conflict, Forbidden, NotFound

OPEN_ROUND_TITLE = 'Открытый раунд Arena'
OPEN_ROUND_MINUTES = 45  # таймер участника открытого раунда
WRONG_PENALTY_MINUTES = 20  # штраф за неверную попытку до верной (как в ICPC)
DEFAULT_FREEZE_MINUTES = 15
MIN_DURATION, MAX_DURATION = 15, 240


# ── Раунды ───────────────────────────────────────────────────────────────────
async def ensure_open_round(session: AsyncSession) -> ArenaRound:
    stmt = select(ArenaRound).where(ArenaRound.is_open.is_(True), ArenaRound.company_id.is_(None))
    r = (await session.execute(stmt)).scalars().first()
    if r is None:
        r = ArenaRound(
            title=OPEN_ROUND_TITLE,
            description=(
                'Постоянный раунд: таймер запускается, когда вы нажимаете «Участвовать». '
                'Подходит для знакомства с Arena.'
            ),
            starts_at=utcnow() - timedelta(minutes=1),
            ends_at=None,
            duration_minutes=OPEN_ROUND_MINUTES,
            is_open=True,
            freeze_minutes=0,
            problems=list(problems.OPEN_ROUND_PROBLEMS),
        )
        session.add(r)
        await session.flush()
    return r


def round_state(r: ArenaRound, now: datetime) -> str:
    if r.is_open:
        return 'running'
    if now < r.starts_at:
        return 'upcoming'
    if r.ends_at is not None and now >= r.ends_at:
        return 'finished'
    return 'running'


def frozen_since(r: ArenaRound) -> datetime | None:
    if r.is_open or not r.freeze_minutes or r.ends_at is None:
        return None
    return r.ends_at - timedelta(minutes=r.freeze_minutes)


def round_out(
    r: ArenaRound,
    now: datetime,
    *,
    participant: ArenaParticipant | None = None,
    sponsor: str | None = None,
    participants: int = 0,
) -> dict[str, Any]:
    return {
        'id': r.id,
        'title': r.title,
        'description': r.description,
        'specialization': r.specialization,
        'specialization_title': SPEC_BY_CODE[r.specialization]['title'] if r.specialization in SPEC_BY_CODE else None,
        'starts_at': r.starts_at,
        'ends_at': r.ends_at,
        'duration_minutes': r.duration_minutes,
        'is_open': r.is_open,
        'freeze_minutes': r.freeze_minutes,
        'state': round_state(r, now),
        'problems': [problems.catalog_item(c) for c in r.problems],
        'sponsor': sponsor,
        'prize': r.prize,
        'participants': participants,
        'participation': participation_out(participant, now) if participant else None,
        'server_time': now,
    }


def participation_out(p: ArenaParticipant, now: datetime) -> dict[str, Any]:
    active = p.finished_at is None and now < p.ends_at
    return {
        'id': p.id,
        'started_at': p.started_at,
        'ends_at': p.ends_at,
        'finished_at': p.finished_at,
        'active': active,
        'seconds_left': max(0, int((p.ends_at - now).total_seconds())) if active else 0,
        'solved': p.solved,
        'penalty': p.penalty,
        'rating_before': p.rating_before,
        'rating_after': p.rating_after,
        'rated': p.rated_at is not None,
    }


async def get_round(session: AsyncSession, round_id: UUID) -> ArenaRound:
    r = await session.get(ArenaRound, round_id)
    if r is None:
        raise NotFound('Раунд')
    return r


async def get_participant(session: AsyncSession, r: ArenaRound, profile: CandidateProfile) -> ArenaParticipant | None:
    stmt = select(ArenaParticipant).where(ArenaParticipant.round_id == r.id, ArenaParticipant.profile_id == profile.id)
    return (await session.execute(stmt)).scalars().first()


async def join(session: AsyncSession, r: ArenaRound, profile: CandidateProfile) -> ArenaParticipant:
    existing = await get_participant(session, r, profile)
    if existing:
        return existing
    now = utcnow()
    state = round_state(r, now)
    if state != 'running':
        raise Conflict('Раунд ещё не начался' if state == 'upcoming' else 'Раунд уже закончился')
    if r.specialization and profile.specialization and profile.specialization != r.specialization:
        raise Forbidden('Раунд проводится для другой специализации')
    if r.is_open:
        starts, ends = now, now + timedelta(minutes=r.duration_minutes)
    else:
        starts, ends = r.starts_at, r.ends_at or r.starts_at + timedelta(minutes=r.duration_minutes)
    p = ArenaParticipant(round_id=r.id, profile_id=profile.id, started_at=starts, ends_at=ends, solved=0, penalty=0)
    session.add(p)
    await session.flush()
    return p


def require_active(p: ArenaParticipant | None, now: datetime) -> ArenaParticipant:
    if p is None:
        raise Conflict('Сначала нажмите «Участвовать»')
    if p.finished_at is not None or now >= p.ends_at:
        raise Conflict('Время участия закончилось: отправка не принимается')
    return p


async def finish(session: AsyncSession, p: ArenaParticipant) -> ArenaParticipant:
    now = utcnow()
    if p.finished_at is None and now < p.ends_at:
        p.finished_at = now
    await finalize(session, p)
    return p


# ── Варианты ─────────────────────────────────────────────────────────────────
def participant_variant(r: ArenaRound, profile_id: UUID, code: str) -> problems.Variant:
    if code not in r.problems:
        raise NotFound('Задача')
    return problems.variant(code, problems.variant_seed(r.id, profile_id, code))


# ── Проверка ─────────────────────────────────────────────────────────────────
def _check_language(language: str) -> None:
    langs = judge.capabilities()['languages']
    if language not in langs:
        raise BadRequest(f'Язык недоступен. Доступно: {", ".join(judge.LANGUAGE_TITLES[x] for x in langs)}')


async def run_samples(
    r: ArenaRound, profile: CandidateProfile, code_name: str, language: str, code: str
) -> dict[str, Any]:
    _check_language(language)
    v = participant_variant(r, profile.id, code_name)
    try:
        res = await judge.judge(language, code, v.samples, show_output=True)
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    return res.to_dict()


async def submit(
    session: AsyncSession,
    r: ArenaRound,
    profile: CandidateProfile,
    code_name: str,
    language: str,
    code: str,
    signals: dict[str, Any],
) -> ArenaSubmission:
    _check_language(language)
    now = utcnow()
    p = require_active(await get_participant(session, r, profile), now)
    v = participant_variant(r, profile.id, code_name)
    if len(code.encode()) > judge.CODE_LIMIT_KB * 1024:
        raise BadRequest(f'Код больше {judge.CODE_LIMIT_KB} КБ')
    clean_signals = {k: int(signals.get(k) or 0) for k in ('paste_chars', 'paste_events', 'blur_count')}
    sub = ArenaSubmission(
        participant_id=p.id,
        round_id=r.id,
        profile_id=profile.id,
        problem=code_name,
        language=language,
        code=code,
        status='running',
        signals=clean_signals,
        minute=max(0, int((now - p.started_at).total_seconds() // 60)),
        tests=[],
    )
    session.add(sub)
    await session.flush()
    sub_id, participant_id = sub.id, p.id
    # Соединение с базой не держим, пока идут тесты
    await session.commit()

    try:
        res = await judge.judge(language, code, v.tests)
    except ValueError as exc:
        sub = await session.get(ArenaSubmission, sub_id)
        sub.status, sub.verdict, sub.message = 'error', 'RE', str(exc)  # type: ignore[union-attr]
        await session.flush()
        raise BadRequest(str(exc)) from exc
    review = await feedback.review(v, language, code, res)

    sub = await session.get(ArenaSubmission, sub_id)  # type: ignore[assignment]
    p = await session.get(ArenaParticipant, participant_id)  # type: ignore[assignment]
    sub.status = 'done'
    sub.verdict = res.verdict
    sub.passed, sub.total = res.passed, res.total
    sub.time_ms, sub.memory_kb = res.time_ms, res.memory_kb
    sub.tests = [{'verdict': t.verdict, 'time_ms': t.time_ms, 'sample': t.sample} for t in res.tests]
    sub.message = res.message
    sub.feedback = review
    sub.judged_at = utcnow()
    await _mark_similar(session, sub)
    await recompute(session, p)
    profile.last_activity_at = utcnow()
    await session.flush()
    return sub


async def _mark_similar(session: AsyncSession, sub: ArenaSubmission) -> None:
    stmt = (
        select(ArenaSubmission)
        .where(
            ArenaSubmission.round_id == sub.round_id,
            ArenaSubmission.problem == sub.problem,
            ArenaSubmission.language == sub.language,
            ArenaSubmission.profile_id != sub.profile_id,
            ArenaSubmission.status == 'done',
        )
        .order_by(ArenaSubmission.created_at.desc())
        .limit(200)
    )
    for other in (await session.execute(stmt)).scalars():
        if similarity.suspicious(sub.language, sub.code, other.code):
            sub.similar_to = other.id
            if other.similar_to is None:
                other.similar_to = sub.id
            return


def score_rows(subs: list[ArenaSubmission], round_problems: list[str]) -> tuple[int, int, dict[str, dict[str, Any]]]:
    """ICPC: решённые задачи и штраф (минута первой верной + штраф за неверные до неё; CE не считается)."""
    cells: dict[str, dict[str, Any]] = {c: {'solved': False, 'attempts': 0, 'minute': None} for c in round_problems}
    for s in sorted(subs, key=lambda x: x.created_at):
        cell = cells.get(s.problem)
        if cell is None or cell['solved'] or s.status != 'done' or s.verdict in (None, 'CE'):
            continue
        if s.verdict == 'OK':
            cell['solved'], cell['minute'] = True, s.minute
        else:
            cell['attempts'] += 1
    solved = sum(c['solved'] for c in cells.values())
    penalty = sum(c['minute'] + WRONG_PENALTY_MINUTES * c['attempts'] for c in cells.values() if c['solved'])
    return solved, penalty, cells


async def recompute(session: AsyncSession, p: ArenaParticipant) -> None:
    r = await session.get(ArenaRound, p.round_id)
    subs = list(
        (await session.execute(select(ArenaSubmission).where(ArenaSubmission.participant_id == p.id))).scalars()
    )
    p.solved, p.penalty, _ = score_rows(subs, r.problems)  # type: ignore[union-attr]
    p.updated_at = utcnow()


def submission_out(s: ArenaSubmission, *, with_code: bool = False) -> dict[str, Any]:
    out = {
        'id': s.id,
        'problem': s.problem,
        'language': s.language,
        'status': s.status,
        'verdict': s.verdict,
        'verdict_title': judge.VERDICT_TITLES.get(s.verdict or '', None),
        'passed': s.passed,
        'total': s.total,
        'time_ms': s.time_ms,
        'memory_kb': s.memory_kb,
        'tests': s.tests or [],
        'message': s.message,
        'feedback': s.feedback,
        'suspicious': s.similar_to is not None,
        'minute': s.minute,
        'created_at': s.created_at,
    }
    if with_code:
        out['code'] = s.code
    return out


# ── Таблица ──────────────────────────────────────────────────────────────────
def display_name(profile: CandidateProfile) -> str:
    privacy = {**DEFAULT_PRIVACY, **(profile.privacy or {})}
    if privacy.get('show_arena') and profile.full_name:
        return profile.full_name
    return public_alias(profile.id).replace('Кандидат', 'Участник')


async def leaderboard(
    session: AsyncSession, r: ArenaRound, *, viewer_profile_id: UUID | None = None, employer: bool = False
) -> dict[str, Any]:
    now = utcnow()
    await finalize_due(session, round_id=r.id)
    rows = (
        await session.execute(
            select(ArenaParticipant, CandidateProfile)
            .join(CandidateProfile, CandidateProfile.id == ArenaParticipant.profile_id)
            .where(ArenaParticipant.round_id == r.id)
        )
    ).all()
    subs = list((await session.execute(select(ArenaSubmission).where(ArenaSubmission.round_id == r.id))).scalars())
    by_participant: dict[UUID, list[ArenaSubmission]] = {}
    for s in subs:
        by_participant.setdefault(s.participant_id, []).append(s)
    freeze = frozen_since(r)
    frozen = bool(freeze and freeze <= now and round_state(r, now) == 'running' and not employer)
    ratings = await ratings_for(session, [p.id for _, p in rows])
    table = []
    for part, prof in rows:
        own = viewer_profile_id == prof.id
        visible = [s for s in by_participant.get(part.id, []) if own or not frozen or s.created_at < freeze]  # type: ignore[operator]
        solved, penalty, cells = score_rows(visible, r.problems)
        rt = ratings.get(prof.id)
        table.append(
            {
                'participant_id': part.id,
                'profile_id': prof.id if (employer or own) else None,
                'name': display_name(prof),
                'me': own,
                'category_title': category_title(prof.specialization, prof.grade) if prof.grade else None,
                'solved': solved,
                'penalty': penalty,
                'cells': cells,
                'suspicious': any(s.similar_to is not None for s in by_participant.get(part.id, []))
                if employer
                else False,
                'arena_rating': round(rt.rating) if rt else None,
                'active': part.finished_at is None and now < part.ends_at,
            }
        )
    table.sort(key=lambda x: (-x['solved'], x['penalty'], x['name']))
    rank = 0
    prev: tuple[int, int] | None = None
    for i, row in enumerate(table, start=1):
        key = (row['solved'], row['penalty'])
        if key != prev:
            rank, prev = i, key
        row['rank'] = rank
    return {
        'round_id': r.id,
        'problems': [problems.catalog_item(c) for c in r.problems],
        'frozen': frozen,
        'frozen_since': freeze if frozen else None,
        'rows': table,
        'version': board_version(subs, len(rows)),
        'server_time': now,
    }


def board_version(subs: list[ArenaSubmission], participants: int) -> str:
    done = [s for s in subs if s.status == 'done']
    last = max((s.judged_at for s in done if s.judged_at), default=None)
    return f'{participants}:{len(done)}:{last.isoformat() if last else "-"}'


async def board_stamp(session: AsyncSession, round_id: UUID) -> str:
    """Дешёвая метка изменений таблицы для SSE."""
    participants = (
        await session.execute(
            select(func.count()).select_from(ArenaParticipant).where(ArenaParticipant.round_id == round_id)
        )
    ).scalar_one()
    done, last = (
        await session.execute(
            select(func.count(), func.max(ArenaSubmission.judged_at)).where(
                ArenaSubmission.round_id == round_id, ArenaSubmission.status == 'done'
            )
        )
    ).one()
    return f'{participants}:{done}:{last.isoformat() if last else "-"}'


# ── Рейтинг ──────────────────────────────────────────────────────────────────
async def ratings_for(session: AsyncSession, profile_ids: list[UUID]) -> dict[UUID, ArenaRating]:
    if not profile_ids:
        return {}
    stmt = select(ArenaRating).where(ArenaRating.profile_id.in_(profile_ids))
    return {x.profile_id: x for x in (await session.execute(stmt)).scalars()}


def current_player(rt: ArenaRating | None, now: datetime) -> rating.Player:
    if rt is None:
        return rating.Player()
    player = rating.Player(rt.rating, rt.rd, rt.volatility)
    if rt.last_round_at:
        player = rating.inflate(player, (now - rt.last_round_at).days)
    return player


async def finalize(session: AsyncSession, p: ArenaParticipant) -> bool:
    """Пересчёт рейтинга по итогам участия (один раз)."""
    now = utcnow()
    if p.rated_at is not None or (p.finished_at is None and now < p.ends_at):
        return False
    subs = list(
        (await session.execute(select(ArenaSubmission).where(ArenaSubmission.participant_id == p.id))).scalars()
    )
    if any(s.status in ('queued', 'running') for s in subs):
        return False
    p.rated_at = now
    judged = [s for s in subs if s.status == 'done' and s.verdict != 'CE']
    if not judged:
        return True  # без отправок рейтинг не меняется
    r = await session.get(ArenaRound, p.round_id)
    _, _, cells = score_rows(subs, r.problems)  # type: ignore[union-attr]
    results = [
        (problems.LEVEL_RATING[problems.PROBLEMS[c].level], rating.PROBLEM_RD, 1.0 if cells[c]['solved'] else 0.0)
        for c in r.problems
    ]  # type: ignore[union-attr]
    rt = (await session.execute(select(ArenaRating).where(ArenaRating.profile_id == p.profile_id))).scalars().first()
    before = current_player(rt, now)
    after = rating.update(before, results)
    if rt is None:
        rt = ArenaRating(
            profile_id=p.profile_id,
            rating=after.rating,
            rd=after.rd,
            volatility=after.volatility,
            rounds=0,
            solved=0,
            history=[],
        )
        session.add(rt)
    rt.rating, rt.rd, rt.volatility = after.rating, after.rd, after.volatility
    rt.rounds = (rt.rounds or 0) + 1
    rt.solved = (rt.solved or 0) + sum(1 for c in cells.values() if c['solved'])
    rt.last_round_at = now
    rt.history = [
        *(rt.history or []),
        {
            'at': now.isoformat(),
            'rating': after.rating,
            'rd': after.rd,
            'round_id': str(p.round_id),
            'round': r.title,
            'solved': p.solved,
        },
    ]  # type: ignore[union-attr]
    p.rating_before, p.rating_after = round(before.rating, 1), after.rating
    profile = await session.get(CandidateProfile, p.profile_id)
    if profile:
        profile.last_activity_at = now
    await session.flush()
    return True


async def finalize_due(session: AsyncSession, *, round_id: UUID | None = None, profile_id: UUID | None = None) -> int:
    now = utcnow()
    stmt = select(ArenaParticipant).where(
        ArenaParticipant.rated_at.is_(None),
        (ArenaParticipant.ends_at <= now) | ArenaParticipant.finished_at.is_not(None),
    )
    if round_id:
        stmt = stmt.where(ArenaParticipant.round_id == round_id)
    if profile_id:
        stmt = stmt.where(ArenaParticipant.profile_id == profile_id)
    done = 0
    for p in list((await session.execute(stmt.limit(100))).scalars()):
        done += await finalize(session, p)
    return done


async def percentile(session: AsyncSession, rt: ArenaRating, specialization: str | None) -> int | None:
    """Доля рейтингов выше — для объяснения «топ-N %»."""
    stmt = select(ArenaRating.rating).join(CandidateProfile, CandidateProfile.id == ArenaRating.profile_id)
    if specialization:
        stmt = stmt.where(CandidateProfile.specialization == specialization)
    values = list((await session.execute(stmt)).scalars())
    if not values:
        return None
    above = sum(1 for v in values if v > rt.rating)
    return max(1, math.ceil(100 * (above + 1) / len(values)))


def rating_out(rt: ArenaRating | None, now: datetime) -> dict[str, Any] | None:
    if rt is None:
        return None
    player = current_player(rt, now)
    return {
        'rating': round(player.rating),
        'rd': round(player.rd),
        'provisional': player.provisional,
        'rounds': rt.rounds,
        'solved': rt.solved,
        'history': rt.history or [],
    }


async def editorial(session: AsyncSession, r: ArenaRound, profile_id: UUID | None) -> list[dict[str, Any]]:
    """Эталоны (вариант зрителя или базовый) и статистика по задачам."""
    subs = list(
        (
            await session.execute(
                select(ArenaSubmission).where(ArenaSubmission.round_id == r.id, ArenaSubmission.status == 'done')
            )
        ).scalars()
    )
    out = []
    for code in r.problems:
        mine = [s for s in subs if s.problem == code]
        tried = {s.profile_id for s in mine if s.verdict != 'CE'}
        solved = {s.profile_id for s in mine if s.verdict == 'OK'}
        v = problems.variant(code, problems.variant_seed(r.id, profile_id or 'editorial', code))
        out.append(
            {
                **problems.catalog_item(code),
                'statement': v.statement,
                'idea': v.problem.idea,
                'complexity': v.problem.complexity,
                'pitfalls': list(v.problem.pitfalls),
                'reference': v.problem.reference(v.params),
                'reference_language': 'python',
                'tried': len(tried),
                'solved': len(solved),
                'submissions': len(mine),
                'solve_rate': round(100 * len(solved) / len(tried)) if tried else None,
            }
        )
    return out


async def create_round(
    session: AsyncSession,
    *,
    company_id: UUID,
    title: str,
    description: str | None,
    specialization: str | None,
    problem_codes: list[str],
    starts_at: datetime,
    duration_minutes: int,
    prize: str | None,
) -> ArenaRound:
    unknown = [c for c in problem_codes if c not in problems.PROBLEMS]
    if unknown or not problem_codes:
        raise BadRequest('Выберите задачи из банка')
    if specialization and specialization not in SPEC_BY_CODE:
        raise BadRequest('Неизвестная специализация')
    if not MIN_DURATION <= duration_minutes <= MAX_DURATION:
        raise BadRequest(f'Длительность от {MIN_DURATION} до {MAX_DURATION} минут')
    now = utcnow()
    if starts_at < now - timedelta(minutes=5):
        raise BadRequest('Время начала уже прошло')
    r = ArenaRound(
        title=title,
        description=description,
        specialization=specialization,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=duration_minutes),
        duration_minutes=duration_minutes,
        is_open=False,
        freeze_minutes=min(DEFAULT_FREEZE_MINUTES, duration_minutes // 4),
        problems=list(dict.fromkeys(problem_codes)),
        company_id=company_id,
        prize=prize,
    )
    session.add(r)
    await session.flush()
    return r
