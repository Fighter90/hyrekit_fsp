"""Симуляция кандидатов для демо-данных и валидации методики.

Модельный кандидат с истинной способностью θ отвечает на задание сложности b
верно с вероятностью σ(θ − b) — это та же модель Раша, по которой движок
оценивает способность. Симуляция используется в двух местах:

* `app.core.seed` — правдоподобные результаты тестов у демо-кандидатов;
* `scripts/validate.py` — проверка надёжности и точности классификации.
"""

from __future__ import annotations

import math
import random
from typing import Any

from app.assessment import engine
from app.assessment.bank import Item


def wrong_answer(item: Item) -> Any:
    """Гарантированно неверный ответ того же формата."""
    if item.kind == 'single':
        return str((int(item.answer) + 1) % max(2, len(item.options)))
    if item.kind == 'multi':
        given = set(item.answer)
        given ^= {0}
        return sorted(given) or [1]
    return float(item.answer) + 1


def correct_answer(item: Item) -> Any:
    if item.kind == 'single':
        return str(item.answer)
    if item.kind == 'multi':
        return list(item.answer)
    return item.answer


def answer_attempt(planned: list[engine.PlannedItem], theta: float, rng: random.Random) -> dict[str, Any]:
    """Ответы модельного кандидата на план попытки."""
    answers: dict[str, Any] = {}
    for p in planned:
        item = engine.materialize(p)
        prob = 1.0 / (1.0 + math.exp(-(theta - engine.difficulty(item.level))))
        answers[p.id] = correct_answer(item) if rng.random() < prob else wrong_answer(item)
    return answers


def simulate(specialization: str, grade: str, theta: float, rng: random.Random) -> dict[str, Any]:
    """Полная попытка: план → ответы → оценка и решение по грейду."""
    planned = engine.build_blueprint(specialization, grade, rng_seed=rng.randrange(2**62))
    scored = engine.score_attempt(planned, answer_attempt(planned, theta, rng))
    decision = engine.decide(scored['ability'], grade, None)
    return {**scored, 'passed': decision.passed, 'suggestion': decision.suggestion}
