"""Механика тестирования: blueprint, оценка способности (Rasch/1PL) и грейд.

1. Blueprint. Для специализации берутся её 5 тем, по каждой — 2 задания.
   Уровни заданий привязаны к проверяемому грейду: основной уровень
   `g + 1` и соседний (`g + 2` или `g`), чтобы измерять способность именно
   у границы грейда. Структура одинакова для всех кандидатов грейда, а
   конкретные варианты разные — так сохраняется сопоставимость сложности.
2. Оценка. Каждому уровню соответствует трудность b = level − 3 (логиты).
   Способность θ оценивается методом MAP (Rasch + априорное N(cut(g), 1)),
   что даёт конечную оценку даже при 0 или 100 % верных ответов. Априорное
   распределение стоит на пороге проверяемого грейда: без ответов оценка
   ровно на границе и не подталкивает ни к сдаче, ни к провалу.
3. Решение. Грейд g подтверждён, если θ ≥ cut(g) = g − CUT_OFFSET. Порог стоит
   выше трудности заданий грейда: на 10 заданиях нужно около 6 верных, на 5 —
   3 (у Intern и Lead соседние уровни упираются в края шкалы, поэтому у Intern
   может хватить 5 из 10, а Lead нужно 7 из 10). Если
   θ уверенно выше порога следующего грейда — система предлагает пройти тест
   выше; при провале предлагается грейд ниже. Принудительного понижения нет.
"""

from __future__ import annotations

import math
import secrets
from dataclasses import dataclass
from typing import Any

from app.assessment import bank
from app.catalog.data import GRADE_CODES, GRADE_ORDER, SPEC_BY_CODE

ITEMS_PER_TOPIC = 2
SECONDS_PER_ITEM = 120
EXPRESS_ITEMS_PER_TOPIC = 1  # экспресс-тест для жюри: 5 тем × 1 задание
EXPRESS_SECONDS_PER_ITEM = 60
CUT_OFFSET = 1.75  # cut(g) = g − CUT_OFFSET; на 0.25 логита выше трудности заданий грейда
UPGRADE_MARGIN = 0.35  # запас по θ над порогом следующего грейда
MAX_CONCEPTUAL = 1  # не больше одного концептуального задания в попытке (см. bank.CONCEPTUAL)
CONCEPTUAL_WEIGHT = 1.0  # вес концептуального ответа в оценке θ


def cut(grade: str) -> float:
    """Порог способности для грейда (логиты)."""
    return GRADE_ORDER[grade] - CUT_OFFSET


def difficulty(level: int) -> float:
    return float(level - 3)


@dataclass(frozen=True)
class PlannedItem:
    id: str
    family: str
    topic: str
    level: int
    seed: int


def build_blueprint(
    specialization: str,
    grade: str,
    *,
    rng_seed: int | None = None,
    topics: list[str] | None = None,
    items_per_topic: int = ITEMS_PER_TOPIC,
    excluded: frozenset[str] = frozenset(),
) -> list[PlannedItem]:
    """Формирует план попытки: темы × уровни × случайные семейства и зёрна.

    `excluded` — семейства, которые мониторинг утечек снял с выдачи
    (`assessment.calibration`). Если в теме на уровне других не осталось,
    берутся исключённые: тест без темы хуже, чем тест с известным заданием.
    """
    import random

    rng = random.Random(rng_seed if rng_seed is not None else secrets.randbits(64))
    spec_topics = topics or SPEC_BY_CODE[specialization]['topics']
    base = GRADE_ORDER[grade] + 1  # 1..5
    planned: list[PlannedItem] = []
    conceptual_count = 0
    for t_index, topic in enumerate(spec_topics):
        neighbour = base + 1 if t_index % 2 == 0 else base - 1
        levels = [base, max(1, min(5, neighbour)), base, max(1, min(5, base * 2 - neighbour))][:items_per_topic]
        used: set[str] = set()
        for slot, level in enumerate(levels):
            # Только семейства, осмысленные на этом уровне, — сложность задания равна плановой.
            families = bank.topics(level).get(topic) or bank.topics(level)['algorithms']
            families = [f for f in families if f not in excluded] or families
            fresh = [f for f in families if f not in used] or families
            # Первое задание темы и всё сверх лимита — генеративные, если такие есть
            # (при нехватке семейств допускается то же семейство с другим зерном).
            if slot == 0 or conceptual_count >= MAX_CONCEPTUAL:
                generative = [f for f in fresh if f not in bank.CONCEPTUAL] or [
                    f for f in families if f not in bank.CONCEPTUAL
                ]
                fresh = generative or fresh
            fam = rng.choice(fresh)
            conceptual_count += fam in bank.CONCEPTUAL
            used.add(fam)
            planned.append(PlannedItem(f'q{len(planned) + 1}', fam, topic, level, rng.randrange(2**31)))
    rng.shuffle(planned)
    return planned


def materialize(p: PlannedItem) -> bank.Item:
    return bank.generate(p.family, p.seed, p.level)


PRIOR_SD = 1.0


def estimate_ability(
    responses: list[tuple[float, bool]] | list[tuple[float, bool, float]],
    *,
    prior_mean: float = 0.0,
    prior_sd: float | None = None,
) -> float:
    """MAP-оценка θ для модели Раша. responses: [(b, верно?)] или [(b, верно?, вес)]."""
    prior_sd = prior_sd or PRIOR_SD
    theta = prior_mean
    for _ in range(50):
        grad = -(theta - prior_mean) / prior_sd**2
        hess = -1.0 / prior_sd**2
        for b, correct, *rest in responses:
            w = rest[0] if rest else 1.0
            p = 1.0 / (1.0 + math.exp(-(theta - b)))
            grad += w * ((1.0 if correct else 0.0) - p)
            hess -= w * p * (1 - p)
        step = grad / hess
        theta -= step
        if abs(step) < 1e-6:
            break
    return theta


@dataclass
class Decision:
    passed: bool
    assigned_grade: str | None
    suggestion: str  # keep | retry_lower | try_higher


def decide(theta: float, tested_grade: str, current_grade: str | None) -> Decision:
    """Решение по грейду. Грейд никогда не понижается принудительно."""
    passed = theta >= cut(tested_grade)
    order = GRADE_ORDER[tested_grade]
    if passed:
        nxt = GRADE_CODES[order + 1] if order + 1 < len(GRADE_CODES) else None
        suggestion = 'try_higher' if nxt and theta >= cut(nxt) + UPGRADE_MARGIN else 'keep'
        if current_grade and GRADE_ORDER[current_grade] > order:
            return Decision(True, current_grade, 'keep')
        return Decision(True, tested_grade, suggestion)
    lower = 'retry_lower' if order > 0 else 'keep'
    return Decision(False, current_grade, lower)


def score_attempt(
    planned: list[PlannedItem], answers: dict[str, Any], *, grade: str | None = None, prior_mean: float | None = None
) -> dict[str, Any]:
    """Проверка ответов и агрегаты для результата.

    Априорное среднее — порог проверяемого грейда (`grade`); без грейда — 0.
    """
    if prior_mean is None:
        prior_mean = cut(grade) if grade else 0.0
    responses: list[tuple[float, bool, float]] = []
    by_topic: dict[str, dict[str, int]] = {}
    weighted, weight_total, correct = 0.0, 0.0, 0
    for p in planned:
        item = materialize(p)
        ok = bank.check(item, answers.get(p.id))
        weight = CONCEPTUAL_WEIGHT if p.family in bank.CONCEPTUAL else 1.0
        responses.append((difficulty(item.level), ok, weight))
        correct += ok
        weighted += item.level * ok
        weight_total += item.level
        t = by_topic.setdefault(p.topic, {'correct': 0, 'total': 0})
        t['total'] += 1
        t['correct'] += ok
    theta = estimate_ability(responses, prior_mean=prior_mean)
    return {
        'ability': round(theta, 3),
        'score': round(100 * weighted / weight_total) if weight_total else 0,
        'correct': correct,
        'total': len(planned),
        'by_topic': [{'topic': k, **v} for k, v in by_topic.items()],
    }


def public_item(p: PlannedItem) -> dict[str, Any]:
    """Представление задания для кандидата — без правильного ответа."""
    item = materialize(p)
    return {
        'id': p.id,
        'topic': p.topic,
        'difficulty': item.level,
        'kind': item.kind,
        'stem': item.stem,
        'code': item.code,
        'options': item.options,
    }
