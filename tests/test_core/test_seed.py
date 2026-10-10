"""Демо-данные: аккаунты, банк кандидатов, идемпотентность."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.candidates.models import CandidateProfile
from app.candidates.service import is_visible
from app.core.seed import CANDIDATE_EMAIL, EMPLOYER_EMAIL, SYNTHETIC_COUNT, seed_demo
from app.employers.models import Vacancy


async def test_seed_demo_is_idempotent(session: AsyncSession) -> None:
    await seed_demo(session)
    await seed_demo(session)

    emails = set((await session.execute(select(User.email))).scalars())
    assert {CANDIDATE_EMAIL, EMPLOYER_EMAIL} <= emails
    profiles = (await session.execute(select(CandidateProfile))).scalars().all()
    assert len(profiles) == SYNTHETIC_COUNT
    vacancies = (await session.execute(select(func.count()).select_from(Vacancy))).scalar_one()
    assert vacancies == 3

    visible = [p for p in profiles if is_visible(p)]
    assert len(visible) > SYNTHETIC_COUNT * 0.8
    assert {p.specialization for p in visible} >= {'backend', 'frontend', 'devops'}
    assert any(p.fsp_snapshot and p.fsp_snapshot['achievements'] for p in profiles)
