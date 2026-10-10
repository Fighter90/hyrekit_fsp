"""Тест под вакансию: как система формирует задания по описанию потребности.

ТЗ просит показать на нескольких вакансиях, как из описания получаются задания.
Темы берутся из стека вакансии (технология → тема теста), недостающие
добираются темами специализации. Профиль сложности при этом не меняется:
он задаётся только грейдом и позицией темы в плане, поэтому два варианта
одной вакансии и вариант стандартного теста категории равны по сложности.
"""

from __future__ import annotations

import secrets
from typing import Any

from app.assessment import engine
from app.catalog.data import GRADE_ORDER, SPEC_BY_CODE, TECH_TOPICS, TOPIC_TITLES

TOPICS_PER_TEST = 5


def vacancy_topics(specialization: str, stack: list[str]) -> list[dict[str, Any]]:
    """Темы теста с обоснованием: какие технологии вакансии их потребовали."""
    by_topic: dict[str, list[str]] = {}
    for tech in stack:
        topic = TECH_TOPICS.get(tech.strip().lower())
        if topic:
            by_topic.setdefault(topic, []).append(tech)
    spec_topics = SPEC_BY_CODE[specialization]['topics']
    # Сначала темы, которые подтверждают больше технологий вакансии, затем база специализации.
    ordered = sorted(by_topic, key=lambda t: (-len(by_topic[t]), spec_topics.index(t) if t in spec_topics else 99))
    chosen = ordered[:TOPICS_PER_TEST]
    for t in spec_topics:
        if len(chosen) >= TOPICS_PER_TEST:
            break
        if t not in chosen:
            chosen.append(t)
    return [
        {
            'topic': t,
            'title': TOPIC_TITLES.get(t, t),
            'reason': f'Стек вакансии: {", ".join(by_topic[t])}' if t in by_topic else 'Базовая тема специализации',
        }
        for t in chosen
    ]


def preview(specialization: str, grade: str, stack: list[str], *, variants: int = 2) -> dict[str, Any]:
    """Несколько вариантов теста по вакансии — разные задания, одинаковая сложность."""
    topics = vacancy_topics(specialization, stack)
    codes = [t['topic'] for t in topics]
    out = []
    for _ in range(variants):
        plan = engine.build_blueprint(specialization, grade, rng_seed=secrets.randbits(62), topics=codes)
        items = [engine.public_item(p) for p in sorted(plan, key=lambda p: (codes.index(p.topic), p.level))]
        out.append({'items': items, 'difficulty_profile': sorted(i['difficulty'] for i in items)})
    return {
        'specialization': specialization,
        'grade': grade,
        'grade_level': GRADE_ORDER[grade] + 1,
        'topics': topics,
        'seconds': engine.SECONDS_PER_ITEM * len(out[0]['items']),
        'variants': out,
    }
