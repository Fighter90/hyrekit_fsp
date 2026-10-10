"""Сценарий тестирования кандидата: допуск, старт, ответы, завершение."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment import calibration, engine
from app.assessment.models import AssessmentAttempt, ItemCalibration
from app.candidates.models import CandidateProfile
from app.candidates.service import next_grade_change_at, touch, utcnow
from app.catalog.data import GRADE_CODES, category_code
from app.core.exceptions import BadRequest, Conflict, NotFound

logger = logging.getLogger(__name__)


def eligibility(profile: CandidateProfile) -> dict[str, Any]:
    """Какие грейды можно сдавать сейчас.

    Пока грейд не подтверждён, доступен любой (после провала — сразу ниже).
    После подтверждения смена грейда возможна не чаще раза в 90 дней.
    Гость экспресс-теста сдаёт любой грейд без кулдауна.
    """
    base = {'declared_grade': profile.declared_grade, 'current_grade': profile.grade}
    if not profile.specialization:
        return {
            **base,
            'allowed_grades': [],
            'locked_until': None,
            'reason': 'Сначала пройдите опрос: отрасль, специализация, грейд',
        }
    if profile.grade is None or profile.is_guest:
        return {**base, 'allowed_grades': list(GRADE_CODES), 'locked_until': None, 'reason': None}
    unlock = next_grade_change_at(profile)
    if unlock and unlock > utcnow():
        return {
            **base,
            'allowed_grades': [],
            'locked_until': unlock,
            'reason': 'Грейд можно менять не чаще одного раза в 90 дней',
        }
    others = [g for g in GRADE_CODES if g != profile.grade]
    return {**base, 'allowed_grades': others, 'locked_until': None, 'reason': None}


def _plan(attempt: AssessmentAttempt) -> list[engine.PlannedItem]:
    return [engine.PlannedItem(**p) for p in attempt.plan]


def view(attempt: AssessmentAttempt) -> dict[str, Any]:
    return {
        'id': attempt.id,
        'grade': attempt.grade,
        'mode': attempt.mode,
        'specialization': attempt.specialization,
        'started_at': attempt.started_at,
        'deadline_at': attempt.deadline_at,
        'items': [engine.public_item(p) for p in _plan(attempt)],
        'answers': attempt.answers or {},
    }


def result(attempt: AssessmentAttempt) -> dict[str, Any]:
    return {
        'id': attempt.id,
        'grade_tested': attempt.grade,
        'mode': attempt.mode,
        'specialization': attempt.specialization,
        'score': attempt.score,
        'ability': attempt.ability,
        'correct': attempt.correct,
        'total': attempt.total,
        'passed': attempt.passed,
        'assigned_grade': attempt.assigned_grade,
        'suggestion': attempt.suggestion,
        'by_topic': attempt.by_topic or [],
        'finished_at': attempt.finished_at,
    }


async def active_attempt(session: AsyncSession, profile: CandidateProfile) -> AssessmentAttempt | None:
    stmt = (
        select(AssessmentAttempt)
        .where(AssessmentAttempt.profile_id == profile.id, AssessmentAttempt.finished_at.is_(None))
        .order_by(AssessmentAttempt.started_at.desc())
    )
    return (await session.execute(stmt)).scalars().first()


async def start(session: AsyncSession, profile: CandidateProfile, grade: str) -> AssessmentAttempt:
    if grade not in GRADE_CODES:
        raise BadRequest('Неизвестный грейд')
    elig = eligibility(profile)
    if grade not in elig['allowed_grades']:
        raise Conflict(elig['reason'] or 'Этот грейд сейчас недоступен для теста')
    current = await active_attempt(session, profile)
    if current and current.deadline_at > utcnow() and current.grade == grade:
        return current  # продолжение незавершённой попытки
    if current:
        await finish(session, profile, current)  # просроченная или другой грейд — закрываем
    # Гость сдаёт экспресс-тест (FSP-32), обычный кандидат — полный.
    express = profile.is_guest
    plan = engine.build_blueprint(
        profile.specialization,  # type: ignore[arg-type]
        grade,
        items_per_topic=engine.EXPRESS_ITEMS_PER_TOPIC if express else engine.ITEMS_PER_TOPIC,
        excluded=await excluded_families(session),
    )
    seconds = engine.EXPRESS_SECONDS_PER_ITEM if express else engine.SECONDS_PER_ITEM
    now = utcnow()
    attempt = AssessmentAttempt(
        profile_id=profile.id,
        specialization=profile.specialization,
        grade=grade,
        mode='express' if express else 'full',
        plan=[p.__dict__ for p in plan],
        answers={},
        started_at=now,
        deadline_at=now + timedelta(seconds=seconds * len(plan)),
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def get_attempt(session: AsyncSession, profile: CandidateProfile, attempt_id: UUID) -> AssessmentAttempt:
    attempt = await session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.profile_id != profile.id:
        raise NotFound('Попытка')
    return attempt


def save_answer(attempt: AssessmentAttempt, item_id: str, answer: Any) -> None:
    if attempt.finished_at is not None:
        raise Conflict('Попытка уже завершена')
    if attempt.deadline_at < utcnow():
        raise Conflict('Время на тест истекло')
    if item_id not in {p['id'] for p in attempt.plan}:
        raise NotFound('Задание')
    attempt.answers = {**(attempt.answers or {}), item_id: answer}


async def finish(session: AsyncSession, profile: CandidateProfile, attempt: AssessmentAttempt) -> AssessmentAttempt:
    if attempt.finished_at is not None:
        return attempt
    scored = engine.score_attempt(_plan(attempt), attempt.answers or {}, grade=attempt.grade)
    decision = engine.decide(scored['ability'], attempt.grade, profile.grade)
    now = utcnow()
    attempt.finished_at = now
    attempt.score = scored['score']
    attempt.ability = scored['ability']
    attempt.correct = scored['correct']
    attempt.total = scored['total']
    attempt.by_topic = scored['by_topic']
    attempt.passed = decision.passed
    attempt.assigned_grade = decision.assigned_grade
    attempt.suggestion = decision.suggestion

    if decision.passed and decision.assigned_grade == attempt.grade:
        if profile.grade != attempt.grade:
            profile.grade_changed_at = now
        profile.grade = attempt.grade
        profile.category = category_code(attempt.specialization, attempt.grade)
        profile.test_score = scored['score']
        profile.ability = scored['ability']
    touch(profile)
    await session.flush()
    return attempt


async def history(session: AsyncSession, profile: CandidateProfile) -> list[AssessmentAttempt]:
    stmt = (
        select(AssessmentAttempt)
        .where(AssessmentAttempt.profile_id == profile.id, AssessmentAttempt.finished_at.is_not(None))
        .order_by(AssessmentAttempt.finished_at.desc())
    )
    return list((await session.execute(stmt)).scalars())


# ── Мониторинг утечек (FSP-33) ───────────────────────────────────────────────
async def excluded_families(session: AsyncSession) -> frozenset[str]:
    """Семейства, снятые с выдачи последней калибровкой."""
    stmt = select(ItemCalibration.family).where(ItemCalibration.excluded.is_(True))
    return frozenset((await session.execute(stmt)).scalars())


async def recalibrate(
    session: AsyncSession, *, window_days: int = calibration.WINDOW_DAYS, now: Any = None
) -> list[calibration.FamilyStat]:
    """Пересчёт статистики семейств по попыткам за окно и запись статусов.

    Семейства, которых в окне не было, сохраняют прежний статус: утечка
    снимается только новыми данными, а не отсутствием показов.
    """
    now = now or utcnow()
    stmt = select(AssessmentAttempt).where(
        AssessmentAttempt.finished_at.is_not(None),
        AssessmentAttempt.finished_at >= now - timedelta(days=window_days),
    )
    observations: list[calibration.Observation] = []
    for attempt in (await session.execute(stmt)).scalars():
        observations += calibration.attempt_observations(_plan(attempt), attempt.answers or {}, attempt.grade)
    stats = calibration.family_stats(observations)
    rows = {r.family: r for r in (await session.execute(select(ItemCalibration))).scalars()}
    for s in stats:
        row = rows.get(s.family)
        if row is None:
            row = ItemCalibration(family=s.family)
            session.add(row)
        row.topic = s.topic
        row.shows = s.shows
        row.correct = s.correct
        row.solve_rate = round(s.solve_rate, 4)
        row.expected_rate = round(s.expected_rate, 4)
        row.drift = round(s.drift, 4)
        row.z = round(s.z, 2)
        row.offset = round(s.offset, 3)
        row.status = s.status
        row.excluded = s.excluded
        row.calibrated_at = now
    await session.flush()
    return stats


CALIBRATION_LOCK = 33_0033  # ключ advisory-lock PostgreSQL: калибровку ведёт один воркер


async def run_calibration() -> list[calibration.FamilyStat] | None:
    """Калибровка в отдельной транзакции; на PostgreSQL — под advisory-lock."""
    from sqlalchemy import text

    from app.core.database import get_session_factory

    async with get_session_factory()() as session:
        if session.bind.dialect.name == 'postgresql':
            locked = (
                await session.execute(text('SELECT pg_try_advisory_xact_lock(:k)'), {'k': CALIBRATION_LOCK})
            ).scalar()
            if not locked:
                return None
        stats = await recalibrate(session)
        await session.commit()
    leaks = [s.family for s in stats if s.excluded]
    if leaks:
        logger.warning('Мониторинг утечек: исключены семейства %s', ', '.join(leaks))
    return stats


async def calibration_loop(interval_minutes: int) -> None:
    """Периодическая калибровка: первый прогон через минуту после старта."""
    await asyncio.sleep(60)
    while True:
        try:
            await run_calibration()
        except Exception:
            logger.warning('Калибровка заданий не удалась', exc_info=True)
        await asyncio.sleep(interval_minutes * 60)
