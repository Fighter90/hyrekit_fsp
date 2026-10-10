"""Калибровка заданий и мониторинг утечек (FSP-33)."""

from __future__ import annotations

import random
from datetime import timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select

from app.assessment import calibration, engine
from app.assessment.models import AssessmentAttempt, ItemCalibration
from app.assessment.service import excluded_families, recalibrate
from app.assessment.simulate import answer_attempt, correct_answer
from app.candidates.models import CandidateProfile
from app.candidates.service import utcnow
from app.catalog.data import GRADE_CODES

SPEC = 'backend'


def _attempts(n: int, rng: random.Random, leaked: str | None = None, share: float = 0.0, grade: str | None = None):  # type: ignore[no-untyped-def]
    for _ in range(n):
        g = grade or rng.choice(GRADE_CODES)
        theta = engine.cut(g) + 0.5 + rng.gauss(0, 1)
        plan = engine.build_blueprint(SPEC, g, rng_seed=rng.randrange(2**62))
        answers = answer_attempt(plan, theta, rng)
        if leaked and rng.random() < share:
            for p in plan:
                if p.family == leaked:
                    answers[p.id] = correct_answer(engine.materialize(p))
        yield g, plan, answers


def _stats(attempts) -> list[calibration.FamilyStat]:  # type: ignore[no-untyped-def]
    obs: list[calibration.Observation] = []
    for g, plan, answers in attempts:
        obs += calibration.attempt_observations(plan, answers, g)
    return calibration.family_stats(obs)


def _popular_generative(rng: random.Random, grade: str = 'middle') -> str:
    shows: dict[str, int] = {}
    for _, plan, _ in _attempts(200, rng, grade=grade):
        for p in plan:
            if p.family not in engine.bank.CONCEPTUAL:
                shows[p.family] = shows.get(p.family, 0) + 1
    return max(shows, key=lambda f: shows[f])


def test_honest_population_has_no_leaks() -> None:
    stats = _stats(_attempts(800, random.Random(1)))
    assert stats
    assert not [s.family for s in stats if s.status == 'leak']


def test_simulated_leak_is_detected_and_easier() -> None:
    rng = random.Random(2)
    leaked = _popular_generative(rng)
    stats = {s.family: s for s in _stats(_attempts(800, rng, leaked, share=0.5))}
    target = stats[leaked]
    assert target.status == 'leak'
    assert target.excluded
    assert target.drift > calibration.DRIFT_THRESHOLD
    assert target.offset < 0  # утёкшее семейство «легче» номинала
    assert not [f for f, s in stats.items() if f != leaked and s.status == 'leak']


def test_few_shows_give_no_verdict() -> None:
    stats = _stats(_attempts(3, random.Random(3)))
    assert all(s.status == 'few' for s in stats)


def test_blueprint_skips_excluded_families() -> None:
    leaked = _popular_generative(random.Random(4))
    for seed in range(50):
        plan = engine.build_blueprint(SPEC, 'middle', rng_seed=seed, excluded=frozenset({leaked}))
        assert leaked not in {p.family for p in plan}


async def test_recalibrate_persists_status_and_start_avoids_leak(client: AsyncClient, session) -> None:  # type: ignore[no-untyped-def]
    r = await client.post(
        '/api/v1/auth/register',
        json={
            'email': f'cal-{uuid4().hex[:8]}@example.com',
            'password': 'StrongPass1',
            'full_name': 'Тест',
            'role': 'candidate',
        },
    )
    h = {'Authorization': f'Bearer {r.json()["access_token"]}'}
    await client.post(
        '/api/v1/candidate/assessment/survey',
        headers=h,
        json={'industry': 'other', 'specialization': SPEC, 'experience_years': 3, 'declared_grade': 'middle'},
    )
    newest = select(CandidateProfile).order_by(CandidateProfile.created_at.desc())
    profile = (await session.execute(newest)).scalars().first()
    rng = random.Random(5)
    leaked = _popular_generative(rng)
    now = utcnow()
    for g, plan, answers in _attempts(400, rng, leaked, share=0.6, grade='middle'):
        session.add(
            AssessmentAttempt(
                profile_id=profile.id,
                specialization=SPEC,
                grade=g,
                plan=[p.__dict__ for p in plan],
                answers=answers,
                started_at=now - timedelta(hours=1),
                deadline_at=now,
                finished_at=now - timedelta(minutes=30),
            )
        )
    # старая попытка за окном не участвует
    session.add(
        AssessmentAttempt(
            profile_id=profile.id,
            specialization=SPEC,
            grade='middle',
            plan=[{'id': 'q1', 'family': 'nonexistent', 'topic': 'x', 'level': 3, 'seed': 1}],
            answers={},
            started_at=now - timedelta(days=200),
            deadline_at=now - timedelta(days=200),
            finished_at=now - timedelta(days=200),
        )
    )
    await session.flush()

    stats = await recalibrate(session, now=now)
    assert leaked in {s.family for s in stats if s.excluded}
    row = (await session.execute(select(ItemCalibration).where(ItemCalibration.family == leaked))).scalar_one()
    assert row.status == 'leak'
    assert row.excluded
    assert row.shows >= calibration.MIN_SHOWS
    assert leaked in await excluded_families(session)

    view = (await client.post('/api/v1/candidate/assessment/start', json={'grade': 'middle'}, headers=h)).json()
    attempt = await session.get(AssessmentAttempt, __import__('uuid').UUID(view['id']))
    assert leaked not in {p['family'] for p in attempt.plan}
