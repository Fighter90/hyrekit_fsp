"""Калибровка семейств заданий и мониторинг утечек (FSP-33).

Вторая линия защиты после генеративных заданий: если семейство вдруг стало
решаться заметно лучше, чем предсказывает модель Раша, его ответы, вероятно,
разошлись по сети. Такое семейство помечается и исключается из выдачи.

1. Наблюдения. Для каждого ответа в завершённой попытке способность θ
   оценивается заново только по генеративным заданиям той же попытки, без
   самого задания (leave-one-out). Так утёкшее задание не завышает θ, по
   которой его же и проверяют, а концептуальные задания, которые утекают
   первыми, не участвуют в оценке.
2. Ожидание. Вероятность верного ответа p = σ(θ − b), где b — номинальная
   трудность уровня задания (`engine.difficulty`).
3. Дрейф. Для семейства: доля верных минус средняя ожидаемая. MAP-оценка θ
   стянута к порогу грейда, поэтому у всех семейств есть общий сдвиг; он
   вычитается как медиана дрейфа по семействам с достаточным числом показов.
   Остаток — дрейф семейства относительно остальных.
4. Решение. Семейство с дрейфом выше `DRIFT_THRESHOLD` и z-статистикой выше
   `Z_THRESHOLD` при не меньше чем `MIN_SHOWS` показах получает статус
   `leak` и исключается из плана попытки. Обратный дрейф (`hard`) — сигнал
   пересмотреть трудность, задание не исключается.
5. Калибровка. Сдвиг трудности семейства δ (логиты) — MAP-оценка с
   априорным N(0, `OFFSET_PRIOR_SD`): b = b_номинальная + δ.

Модуль — чистые функции без базы: их используют сервис, CLI
`scripts/calibrate.py` и `scripts/validate.py`.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.assessment import bank, engine

DRIFT_THRESHOLD = 0.10  # доля верных выше ожидаемой на 10 п.п. (обоснование — docs/validation/results.md, раздел 6)
Z_THRESHOLD = 4.0  # и отклонение не объясняется случайностью
MIN_SHOWS = 40  # меньше показов — статус few, решение не принимается
OFFSET_PRIOR_SD = 0.5  # априорный разброс сдвига трудности семейства, логиты
WINDOW_DAYS = 60  # окно наблюдений: утечка — событие, старые ответы её размывают


@dataclass(frozen=True)
class Observation:
    family: str
    level: int
    theta: float
    correct: bool


@dataclass
class FamilyStat:
    family: str
    topic: str
    conceptual: bool
    shows: int
    correct: int
    expected: float  # сумма ожидаемых вероятностей
    variance: float  # сумма p(1 − p)
    offset: float = 0.0  # сдвиг трудности δ, логиты
    drift: float = 0.0  # доля верных − ожидаемая − общий сдвиг
    z: float = 0.0
    status: str = 'few'  # ok | leak | hard | few

    @property
    def solve_rate(self) -> float:
        return self.correct / self.shows if self.shows else 0.0

    @property
    def expected_rate(self) -> float:
        return self.expected / self.shows if self.shows else 0.0

    @property
    def excluded(self) -> bool:
        return self.status == 'leak'

    def to_dict(self) -> dict[str, Any]:
        return {
            'family': self.family,
            'topic': self.topic,
            'conceptual': self.conceptual,
            'shows': self.shows,
            'correct': self.correct,
            'solve_rate': round(self.solve_rate, 4),
            'expected_rate': round(self.expected_rate, 4),
            'drift': round(self.drift, 4),
            'z': round(self.z, 2),
            'offset': round(self.offset, 3),
            'status': self.status,
        }


def _p(theta: float, b: float) -> float:
    return 1.0 / (1.0 + math.exp(-(theta - b)))


def attempt_observations(planned: list[engine.PlannedItem], answers: dict[str, Any], grade: str) -> list[Observation]:
    """Наблюдения одной попытки: для каждого задания θ по остальным генеративным."""
    rows = []
    for p in planned:
        item = engine.materialize(p)
        rows.append((p, engine.difficulty(item.level), bank.check(item, answers.get(p.id)), item.level))
    prior = engine.cut(grade)
    out = []
    for i, (p, _b, ok, level) in enumerate(rows):
        anchor = [(b, c) for j, (q, b, c, _) in enumerate(rows) if j != i and q.family not in bank.CONCEPTUAL]
        theta = engine.estimate_ability(anchor, prior_mean=prior)
        out.append(Observation(p.family, level, theta, ok))
    return out


def _offset(obs: list[Observation]) -> float:
    """MAP-оценка сдвига трудности семейства δ методом Ньютона."""
    delta = 0.0
    for _ in range(50):
        grad = -delta / OFFSET_PRIOR_SD**2
        hess = -1.0 / OFFSET_PRIOR_SD**2
        for o in obs:
            p = _p(o.theta, engine.difficulty(o.level) + delta)
            grad += p - (1.0 if o.correct else 0.0)  # d/dδ log-правдоподобия
            hess -= p * (1 - p)
        step = grad / hess
        delta -= step
        if abs(step) < 1e-6:
            break
    return delta


def family_stats(observations: Iterable[Observation]) -> list[FamilyStat]:
    """Статистика и статус по семействам."""
    by_family: dict[str, list[Observation]] = {}
    for o in observations:
        by_family.setdefault(o.family, []).append(o)
    stats: list[FamilyStat] = []
    for fam, obs in by_family.items():
        probs = [_p(o.theta, engine.difficulty(o.level)) for o in obs]
        stats.append(
            FamilyStat(
                family=fam,
                topic=bank.FAMILIES[fam][0] if fam in bank.FAMILIES else '',
                conceptual=fam in bank.CONCEPTUAL,
                shows=len(obs),
                correct=sum(o.correct for o in obs),
                expected=sum(probs),
                variance=sum(p * (1 - p) for p in probs),
                offset=_offset(obs),
            )
        )
    enough = [s for s in stats if s.shows >= MIN_SHOWS]
    shift = statistics.median(s.solve_rate - s.expected_rate for s in enough) if enough else 0.0
    for s in stats:
        s.drift = s.solve_rate - s.expected_rate - shift
        sd = math.sqrt(s.variance) if s.variance > 0 else 1.0
        s.z = (s.correct - s.expected - shift * s.shows) / sd
        if s.shows < MIN_SHOWS:
            s.status = 'few'
        elif s.drift > DRIFT_THRESHOLD and s.z > Z_THRESHOLD:
            s.status = 'leak'
        elif s.drift < -DRIFT_THRESHOLD and s.z < -Z_THRESHOLD:
            s.status = 'hard'
        else:
            s.status = 'ok'
    return sorted(stats, key=lambda s: (-s.drift, s.family))


STATUS_TITLES = {
    'ok': 'в норме',
    'leak': 'утечка, исключено из выдачи',
    'hard': 'сложнее ожидаемого',
    'few': 'мало показов',
}
