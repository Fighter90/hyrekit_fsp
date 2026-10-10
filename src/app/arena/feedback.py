"""Разбор решения после проверки.

Сначала строится разбор по правилам: вердикт, первый непройденный тест и
его вид, типичные ошибки задачи, статический разбор кода (вложенные циклы,
медленный ввод, pop(0), поиск в списке в цикле, рекурсия). Если настроен
GigaChat, модель получает условие, код и итоги тестов и пишет разбор как
ревьюер; при ошибке модели остаётся разбор по правилам. Вердикт всегда
ставят тесты, модель только объясняет.
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any

from app.arena.judge import TIME_LIMIT_S, VERDICT_TITLES, JudgeResult
from app.arena.problems import Variant
from app.llm.gigachat import get_llm

logger = logging.getLogger(__name__)

LARGE_INPUT_BYTES = 100_000

REVIEW_PROMPT = (
    'Ты опытный ревьюер решений олимпиадных задач. Тесты уже проверили код, вердикт не меняй. '
    'Объясни кандидату по-русски, в чём причина результата, оцени асимптотику решения и дай 2-4 конкретных совета. '
    'Не пиши готовое решение целиком. Верни JSON {"summary": "1-2 предложения", "points": ["совет", ...]}.'
)


def _loop_depth(node: ast.AST, depth: int = 0) -> int:
    best = depth
    for child in ast.iter_child_nodes(node):
        inner = depth + 1 if isinstance(child, ast.For | ast.While | ast.comprehension) else depth
        best = max(best, _loop_depth(child, inner))
    return best


def python_notes(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    notes: list[str] = []
    depth = _loop_depth(tree)
    if depth >= 2:
        notes.append(
            f'В коде {depth} вложенных цикла: на больших входах это O(n^{depth}). '
            'Подумайте, как обойтись одним проходом.'
        )
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    names = {getattr(c.func, 'id', None) or getattr(c.func, 'attr', None) for c in calls}
    in_loop_input = any(
        isinstance(n, ast.For | ast.While)
        and any(isinstance(c, ast.Call) and getattr(c.func, 'id', None) == 'input' for c in ast.walk(n))
        for n in ast.walk(tree)
    )
    if in_loop_input:
        notes.append(
            'input() в цикле медленный на больших данных: '
            'читайте весь ввод сразу через sys.stdin.buffer.read().split().'
        )
    if any(
        isinstance(c.func, ast.Attribute)
        and c.func.attr == 'pop'
        and c.args
        and isinstance(c.args[0], ast.Constant)
        and c.args[0].value == 0
        for c in calls
    ):
        notes.append('list.pop(0) работает за O(n). Для очереди используйте collections.deque.popleft().')
    if any(isinstance(c.func, ast.Attribute) and c.func.attr in ('index', 'count') for c in calls) and depth >= 1:
        notes.append('list.index/count внутри цикла — скрытый второй цикл. Словарь или множество дадут O(1).')
    funcs = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)}
    if any(
        getattr(c.func, 'id', None) in funcs
        for f in ast.walk(tree)
        if isinstance(f, ast.FunctionDef)
        for c in ast.walk(f)
        if isinstance(c, ast.Call) and getattr(c.func, 'id', None) == f.name
    ):
        notes.append(
            'Есть рекурсия: глубина стека в Python ограничена, на длинных цепочках надёжнее итеративный вариант.'
        )
    if 'sort' in names or 'sorted' in names:
        notes.append('Сортировка стоит O(n log n): проверьте, нужна ли она для ответа.')
    return notes


def javascript_notes(code: str) -> list[str]:
    notes: list[str] = []
    if re.search(r'for\s*\([^)]*\)[^{]*\{[^}]*for\s*\(', code, re.S):
        notes.append(
            'Вложенные циклы for: на больших входах это квадратичное время. Подумайте, как обойтись одним проходом.'
        )
    if '.shift()' in code:
        notes.append('Array.shift() работает за O(n). Для очереди храните индекс начала.')
    if re.search(r'\.indexOf\(|\.includes\(', code) and 'for' in code:
        notes.append('indexOf/includes в цикле — скрытый второй цикл. Map или Set дадут O(1).')
    return notes


def rules_feedback(variant: Variant, language: str, code: str, result: JudgeResult) -> dict[str, Any]:
    problem = variant.problem
    points: list[str] = []
    bad_index = next((i for i, t in enumerate(result.tests) if t.verdict != 'OK'), None)
    if result.verdict == 'OK':
        summary = (
            f'Все {result.total} тестов пройдены, максимальное время {result.time_ms} мс из {int(TIME_LIMIT_S * 1000)}.'
        )
        points.append(f'Ожидаемая сложность — {problem.complexity}. {problem.idea}')
    elif result.verdict == 'CE':
        summary = 'Код не запустился: синтаксическая ошибка. Строка указана в сообщении об ошибке.'
    else:
        case = variant.tests[bad_index] if bad_index is not None and bad_index < len(variant.tests) else None
        kind = (
            'пример из условия'
            if case and case.sample
            else ('большой тест' if case and len(case.input) > LARGE_INPUT_BYTES else 'скрытый тест')
        )
        where = bad_index + 1 if bad_index is not None else '?'
        summary = (
            f'{VERDICT_TITLES[result.verdict]} на тесте {where} ({kind}). Пройдено {result.passed} из {result.total}.'
        )
        if result.verdict == 'TLE' or (case and len(case.input) > LARGE_INPUT_BYTES and result.verdict != 'WA'):
            points.append(f'Нужна сложность {problem.complexity}. {problem.idea}')
        elif result.verdict == 'WA':
            if case and case.sample:
                points.append('Ответ не совпал уже на примере: сверьте формат вывода и условие задачи.')
            points.append('Типичные ошибки в этой задаче: ' + '; '.join(problem.pitfalls) + '.')
        elif result.verdict == 'MLE':
            points.append('Не храните лишние копии данных: читайте ввод один раз и обрабатывайте на лету.')
        elif result.verdict == 'RE' and result.message:
            last = result.message.strip().splitlines()[-1]
            points.append(f'Причина: {last[:200]}')
    if result.verdict != 'OK':
        # замечания по коду объясняют неудачу; у верного решения они только шумят
        points.extend(python_notes(code) if language == 'python' else javascript_notes(code))
    return {'summary': summary, 'points': points[:5], 'source': 'rules'}


async def review(variant: Variant, language: str, code: str, result: JudgeResult) -> dict[str, Any]:
    base = rules_feedback(variant, language, code, result)
    llm = get_llm()
    if not llm.is_configured or result.verdict == 'CE':
        return base
    tests = ', '.join(f'{i + 1}:{t.verdict}' for i, t in enumerate(result.tests))
    user = (
        f'Задача «{variant.problem.title}» (ожидаемая сложность {variant.problem.complexity}).\n{variant.statement}\n\n'
        f'Язык: {language}. Вердикт: {result.verdict}, пройдено {result.passed}/{result.total}, тесты: {tests}.\n'
        f'Подсказки проверки: {base["summary"]} {" ".join(base["points"])}\n\nКод:\n{code[:6000]}'
    )
    try:
        data = await llm.complete_json(system=REVIEW_PROMPT, user=user)
        points = [str(p)[:400] for p in data.get('points', []) if str(p).strip()][:5]
        summary = str(data.get('summary', '')).strip()[:600]
        if summary:
            return {'summary': summary, 'points': points or base['points'], 'source': 'gigachat'}
    except Exception:
        logger.warning('GigaChat недоступен для разбора решения', exc_info=True)
    return base
