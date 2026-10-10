"""Подбор кандидатов под потребность работодателя.

Выдача строится по категориям (специализация + подтверждённый тестом грейд),
а не по самоописанию резюме. Внутри подборки кандидаты ранжируются по
взвешенной сумме компонентов (все в шкале 0..100):

    score = 0.30·категория + 0.30·стек + 0.25·тест + 0.10·ФСП + 0.05·актуальность

* категория — 100, если грейд внутри диапазона вакансии; соседний грейд
  попадает в подборку со штрафом (рост или запас квалификации);
* стек — доля требуемых технологий, которые есть у кандидата. Требования
  берутся из поля stack и дополнительно извлекаются из текста описания
  (словарь технологий + нормализация синонимов);
* тест — попадание θ в коридор грейдов вакансии (гауссово затухание
  с σ = 0.5 логита за его границами, см. ability_fit);
* ФСП — соревновательный опыт: балл достижений ФСП с учётом релевантности
  дисциплины или рейтинг Code Arena в шкале 0..100 (берётся больший);
* актуальность — свежесть активности (регулярные задания, тесты).

Каждый пункт выдачи сопровождается человекочитаемыми причинами (объяснимость).
"""

from __future__ import annotations

import math
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment.engine import cut
from app.candidates.models import CandidateProfile
from app.candidates.resume_parser import TECH
from app.candidates.service import freshness, fsp_summary, to_card
from app.catalog.data import GRADE_CODES, GRADE_ORDER, GRADE_TITLES, category_title
from app.employers.models import Vacancy

WEIGHTS = {'category': 0.30, 'stack': 0.30, 'test': 0.25, 'fsp': 0.10, 'freshness': 0.05}

SYNONYMS = {
    'js': 'javascript',
    'ts': 'typescript',
    'postgres': 'postgresql',
    'pg': 'postgresql',
    'k8s': 'kubernetes',
    'golang': 'go',
    'react.js': 'react',
    'reactjs': 'react',
    'vue.js': 'vue',
    'node': 'node.js',
    'nodejs': 'node.js',
    'sklearn': 'scikit-learn',
    'torch': 'pytorch',
    'py': 'python',
    'mongo': 'mongodb',
    'ci/cd': 'gitlab ci',
    'yc': 'yandex cloud',
}


def norm(tech: str) -> str:
    t = tech.strip().lower()
    return SYNONYMS.get(t, t)


def extract_stack(text: str) -> list[str]:
    """Технологии, упомянутые в свободном тексте потребности."""
    low = (text or '').lower()
    return [t for t in TECH if re.search(rf'(?<![\w+#.]){re.escape(t.lower())}(?![\w+#])', low)]


def required_stack(vacancy: Vacancy) -> list[str]:
    seen: dict[str, str] = {}
    for t in [*(vacancy.stack or []), *extract_stack(f'{vacancy.description}\n{vacancy.team_description or ""}')]:
        seen.setdefault(norm(t), t)
    return list(seen.values())


def grade_fit(grade: str, gmin: str, gmax: str) -> float:
    g, lo, hi = GRADE_ORDER[grade], GRADE_ORDER[gmin], GRADE_ORDER[gmax]
    if lo <= g <= hi:
        return 100.0
    if g == lo - 1:
        return 55.0  # потенциал роста
    if g == hi + 1:
        return 70.0  # запас квалификации
    return 0.0


def ability_fit(ability: float | None, gmin: str, gmax: str) -> float:
    """Насколько измеренная способность попадает в коридор вакансии, 0..100.

    Коридор — от порога нижнего грейда до порога грейда выше верхнего. Внутри
    коридора 100, снаружи — гауссово затухание с σ = 0.5 логита (порядка
    стандартной ошибки теста). Так «слишком сильный» для junior-вакансии
    кандидат не вытесняет подходящих, а пограничный не отсекается.
    """
    if ability is None:
        return 0.0
    lo, hi = cut(gmin), cut(gmax) + 1.0
    d = lo - ability if ability < lo else max(0.0, ability - hi)
    return 100.0 * math.exp(-(d**2) / (2 * 0.5**2))


def score_candidate(
    profile: CandidateProfile, vacancy: Vacancy, req: list[str], arena: dict[str, Any] | None = None
) -> dict[str, Any]:
    have = {norm(t) for t in profile.stack or []}
    need = list(req)
    matched = [t for t in need if norm(t) in have]
    missing = [t for t in need if norm(t) not in have]
    fsp = fsp_summary(profile)
    parts = {
        'category': grade_fit(profile.grade, vacancy.grade_min, vacancy.grade_max),  # type: ignore[arg-type]
        'stack': 100.0 * len(matched) / len(need) if need else 50.0,
        'test': ability_fit(profile.ability, vacancy.grade_min, vacancy.grade_max),
        'fsp': max(float(fsp['score']) if fsp else 0.0, arena_score(arena)),
        'freshness': freshness(profile),
    }
    total = sum(WEIGHTS[k] * v for k, v in parts.items())

    reasons: list[str] = []
    cat = category_title(profile.specialization, profile.grade)
    if parts['category'] == 100:
        reasons.append(f'Категория {cat} входит в требуемый диапазон')
    elif parts['category'] >= 70:
        reasons.append(f'Грейд {GRADE_TITLES[profile.grade]} выше требуемого — запас квалификации')  # type: ignore[index]
    else:
        reasons.append(f'Грейд {GRADE_TITLES[profile.grade]} на шаг ниже — кандидат с потенциалом роста')  # type: ignore[index]
    if need:
        reasons.append(f'Стек: {len(matched)} из {len(need)}' + (f' ({", ".join(matched[:5])})' if matched else ''))
    if profile.test_score is not None:
        reasons.append(f'Тест на грейд: {profile.test_score:.0f}/100')
    if fsp and fsp['has_history']:
        best = min((a['place'] for a in fsp['achievements'] if a['place']), default=None)
        relevant = sum(1 for a in fsp['achievements'] if a['relevant_to'])
        line = f'ФСП: {len(fsp["achievements"])} соревн.'
        if best:
            line += f', лучшее место — {best}'
        if relevant:
            line += f', профильных — {relevant}'
        reasons.append(line)
    if arena:
        line = f'Arena: рейтинг {arena["rating"]:.0f}'
        if arena.get('top_percent'):
            line += f', топ-{arena["top_percent"]}% специализации'
        if arena.get('provisional'):
            line += ' (предварительный)'
        reasons.append(line)
    if parts['freshness'] >= 100:
        reasons.append('Активен последние 30 дней')
    return {
        'score': round(total, 1),
        'breakdown': {k: round(v, 1) for k, v in parts.items()},
        'reasons': reasons,
        'missing_stack': missing,
    }


def arena_score(arena: dict[str, Any] | None) -> float:
    from app.arena.rating import matching_score

    return matching_score(arena['rating'], arena['rd']) if arena else 0.0


async def arena_ratings(session: AsyncSession, profiles: list[CandidateProfile]) -> dict[Any, dict[str, Any]]:
    """Рейтинг Arena и доля «топ-N %» внутри специализации для объяснения выдачи."""
    from app.arena.models import ArenaRating

    rows = list(
        (
            await session.execute(
                select(ArenaRating, CandidateProfile.specialization).join(
                    CandidateProfile, CandidateProfile.id == ArenaRating.profile_id
                )
            )
        ).all()
    )
    by_spec: dict[Any, list[float]] = {}
    for rt, spec in rows:
        by_spec.setdefault(spec, []).append(rt.rating)
    ids = {p.id for p in profiles}
    out: dict[Any, dict[str, Any]] = {}
    for rt, spec in rows:
        if rt.profile_id not in ids:
            continue
        values = by_spec[spec]
        top = max(1, math.ceil(100 * (sum(1 for v in values if v > rt.rating) + 1) / len(values)))
        out[rt.profile_id] = {'rating': rt.rating, 'rd': rt.rd, 'provisional': rt.rd > 110, 'top_percent': top}
    return out


def _passes_filters(p: CandidateProfile, grade: str | None, stack: list[str], has_fsp: bool | None) -> bool:
    if grade and p.grade != grade:
        return False
    if stack:
        have = {norm(t) for t in p.stack or []}
        if not all(norm(t) in have for t in stack):
            return False
    if has_fsp is not None:
        fsp = fsp_summary(p)
        if bool(fsp and fsp['has_history']) != has_fsp:
            return False
    return True


async def visible_profiles(session: AsyncSession, specialization: str | None = None) -> list[CandidateProfile]:
    stmt = select(CandidateProfile).where(
        CandidateProfile.category.is_not(None), CandidateProfile.consent_given_at.is_not(None)
    )
    if specialization:
        stmt = stmt.where(CandidateProfile.specialization == specialization)
    return list((await session.execute(stmt)).scalars())


async def match_vacancy(
    session: AsyncSession,
    vacancy: Vacancy,
    *,
    grade: str | None = None,
    stack: list[str] | None = None,
    has_fsp: bool | None = None,
    limit: int = 50,
    unlocked: set | None = None,
    statuses: dict | None = None,
) -> dict[str, Any]:
    req = required_stack(vacancy)
    pool = [
        p
        for p in await visible_profiles(session, vacancy.specialization)
        if grade_fit(p.grade, vacancy.grade_min, vacancy.grade_max) > 0  # type: ignore[arg-type]
    ]
    categories: dict[str, dict[str, Any]] = {}
    for p in pool:
        c = categories.setdefault(
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

    items = []
    arena = await arena_ratings(session, pool)
    for p in pool:
        if not _passes_filters(p, grade, stack or [], has_fsp):
            continue
        s = score_candidate(p, vacancy, req, arena.get(p.id))
        items.append(
            {
                'candidate': to_card(
                    p,
                    contacts_unlocked=p.id in (unlocked or set()),
                    invitation_status=(statuses or {}).get(p.id),
                ),
                **s,
            }
        )
    items.sort(key=lambda x: (-x['score'], -(x['candidate']['rating'] or 0)))
    return {
        'vacancy_id': vacancy.id,
        'required_stack': req,
        'base_total': len(pool),  # подборка до уточняющих фильтров: сброс фильтров возвращает её
        'total': len(items),
        'categories': sorted(categories.values(), key=lambda c: GRADE_CODES.index(c['grade'])),
        'items': items[:limit],
    }
