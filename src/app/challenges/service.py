"""Оценка ответов на регулярные короткие задания.

Ответ — решение или описание подхода в свободной форме. При настроенном
GigaChat модель выставляет предварительную оценку по рубрике; без него
используется эвристика (полнота ответа и покрытие ключевых понятий задачи).
Итоговое решение всегда за работодателем, оценка лишь сортирует ответы.
"""

from __future__ import annotations

import logging
import re

from app.llm.gigachat import get_llm

logger = logging.getLogger(__name__)

RUBRIC = (
    'Ты технический интервьюер. Оцени ответ кандидата на короткую задачу по шкале 0-100: '
    'корректность (50), полнота подхода и крайние случаи (30), ясность изложения (20). '
    'Верни JSON {"score": число, "feedback": "1-2 предложения по-русски"}.'
)
WORD_RE = re.compile(r'[a-zа-яё0-9+#]{4,}', re.I)


def heuristic_score(task: str, answer: str) -> tuple[float, str]:
    task_terms = {w.lower() for w in WORD_RE.findall(task)}
    ans_terms = {w.lower() for w in WORD_RE.findall(answer)}
    coverage = len(task_terms & ans_terms) / max(1, min(len(task_terms), 12))
    length = min(1.0, len(answer) / 600)
    has_code = 1.0 if re.search(r'(def |return|select |function|=>|\{|\})', answer, re.I) else 0.0
    score = round(100 * (0.45 * min(coverage, 1) + 0.4 * length + 0.15 * has_code))
    return score, 'Предварительная автоматическая оценка: полнота и покрытие условий задачи.'


async def evaluate(task: str, answer: str) -> tuple[float, str]:
    llm = get_llm()
    if llm.is_configured:
        try:
            data = await llm.complete_json(system=RUBRIC, user=f'Задача:\n{task}\n\nОтвет:\n{answer[:6000]}')
            return max(0.0, min(100.0, float(data.get('score', 0)))), str(data.get('feedback', ''))[:500]
        except Exception:
            logger.warning('LLM недоступна для оценки ответа', exc_info=True)
    return heuristic_score(task, answer)
