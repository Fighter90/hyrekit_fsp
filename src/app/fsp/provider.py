"""Провайдер достижений ФСП.

API реестра ФСП в рамках хакатона не предоставляется, поэтому используется
эмулятор с тем же интерфейсом, что и будущий HTTP-клиент: `fetch(fsp_id)`.
Данные детерминированы по ФСП ID (одинаковый ID → одинаковая история), а ID,
оканчивающиеся на 0, моделируют участника без истории — этот случай система
обязана корректно обрабатывать (ТЗ, п. 2).

Замена на реальный реестр: реализовать `FspProvider` поверх REST/OIDC
(ФСП ID на Keycloak), см. docs/guide/04-arhitektura.md.
"""

from __future__ import annotations

import hashlib
import random
import re
from datetime import UTC, datetime
from typing import Any, Protocol

from app.catalog.data import SPEC_BY_CODE

FSP_ID_RE = re.compile(r'^FSP-\d{4,8}$')

EVENTS = [
    ('Кубок России по спортивному программированию', 'всероссийский', 1.0),
    ('Чемпионат России по спортивному программированию', 'всероссийский', 1.0),
    ('Первенство России по спортивному программированию', 'всероссийский', 0.8),
    ('Региональные соревнования ФСП', 'региональный', 0.5),
    ('Межрегиональный хакатон ФСП', 'межрегиональный', 0.7),
]
DISCIPLINES = [
    'продуктовое программирование',
    'алгоритмическое программирование',
    'информационная безопасность',
    'программирование робототехники',
    'программирование беспилотных систем',
]
ROLES = ['капитан команды', 'участник', 'участник', 'разработчик']
FIRST = ['Алексей', 'Мария', 'Дмитрий', 'Анна', 'Илья', 'Софья', 'Никита', 'Екатерина']
LAST = ['Смирнов', 'Иванова', 'Кузнецов', 'Попова', 'Соколов', 'Лебедева', 'Новиков', 'Морозова']


class FspProvider(Protocol):
    def fetch(self, fsp_id: str) -> dict[str, Any] | None: ...


class MockFspProvider:
    """Детерминированный эмулятор реестра ФСП."""

    def fetch(self, fsp_id: str) -> dict[str, Any] | None:
        if not FSP_ID_RE.match(fsp_id):
            return None
        seed = int(hashlib.sha256(fsp_id.encode()).hexdigest()[:12], 16)
        rng = random.Random(seed)
        name = f'{rng.choice(FIRST)} {rng.choice(LAST)}'
        if fsp_id.endswith('0'):
            return {'fsp_id': fsp_id, 'athlete_name': name, 'achievements': []}
        year_now = datetime.now(UTC).year
        achievements = []
        for _ in range(rng.randint(1, 4)):
            event, level, _ = rng.choice(EVENTS)
            achievements.append(
                {
                    'event': event,
                    'discipline': rng.choice(DISCIPLINES),
                    'level': level,
                    'place': rng.choice([1, 2, 3, 5, 8, 12, None]),
                    'year': year_now - rng.randint(0, 4),
                    'role': rng.choice(ROLES),
                }
            )
        achievements.sort(key=lambda a: -a['year'])
        return {'fsp_id': fsp_id, 'athlete_name': name, 'achievements': achievements}


_provider: FspProvider = MockFspProvider()


def get_provider() -> FspProvider:
    return _provider


def _place_factor(place: int | None) -> float:
    if place is None:
        return 0.35  # участие без призового места
    if place <= 3:
        return 1.0
    if place <= 10:
        return 0.7
    return 0.5


def summarize(raw: dict[str, Any] | None, specialization: str | None) -> dict[str, Any] | None:
    """Сводка для профиля: достижения с релевантностью и итоговый балл 0..100.

    Балл учитывает уровень соревнования, место, давность и — по ответам
    организаторов — релевантность дисциплины специализации кандидата:
    профильная дисциплина весит вдвое больше непрофильной.
    """
    if raw is None:
        return None
    relevant = set(SPEC_BY_CODE.get(specialization or '', {}).get('fsp_disciplines', []))
    year_now = datetime.now(UTC).year
    event_weight = {name: w for name, _, w in EVENTS}
    level_weight = {'всероссийский': 1.0, 'межрегиональный': 0.7, 'региональный': 0.5}
    total = 0.0
    items = []
    for a in raw.get('achievements', []):
        rel = a['discipline'] in relevant
        recency = max(0.4, 1 - 0.15 * (year_now - a['year']))
        weight = event_weight.get(a['event'], level_weight.get(a['level'], 0.5))
        pts = 30 * weight * _place_factor(a['place']) * recency
        total += pts if rel else pts * 0.5
        items.append({**a, 'relevant_to': [specialization] if rel and specialization else []})
    return {
        'fsp_id': raw['fsp_id'],
        'athlete_name': raw.get('athlete_name'),
        'achievements': items,
        'score': round(min(100.0, total)),
        'has_history': bool(items),
    }
