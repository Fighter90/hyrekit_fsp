"""Разбор решения: правила, статический анализ, GigaChat с откатом на правила."""

from __future__ import annotations

from typing import Any

import pytest

from app.arena import feedback
from app.arena.judge import JudgeResult, TestResult
from app.arena.problems import variant


def _result(verdict: str, verdicts: list[str]) -> JudgeResult:
    tests = [TestResult(verdict=v, time_ms=10, memory_kb=1000, sample=i < 2) for i, v in enumerate(verdicts)]
    passed = sum(v == 'OK' for v in verdicts)
    return JudgeResult(verdict=verdict, passed=passed, total=len(verdicts), time_ms=10, memory_kb=1000, tests=tests)


def test_python_notes_find_typical_slowdowns() -> None:
    code = (
        'def f(n):\n    return f(n - 1) if n else 0\n'
        'q = [1, 2]\nfor i in range(3):\n    x = input()\n    for j in q:\n        q.index(j)\n'
        'q.pop(0)\nprint(sorted(q))\n'
    )
    notes = ' '.join(feedback.python_notes(code))
    for marker in ('вложенных цикла', 'input()', 'pop(0)', 'index/count', 'рекурсия', 'Сортировка'):
        assert marker in notes
    assert feedback.python_notes('def (:') == []


def test_javascript_notes() -> None:
    code = 'for (let i=0;i<n;i++) { for (let j=0;j<n;j++) {} }\nq.shift(); a.includes(1)'
    notes = ' '.join(feedback.javascript_notes(code))
    assert 'Вложенные циклы' in notes and 'shift' in notes and 'includes' in notes


def test_rules_feedback_per_verdict() -> None:
    v = variant('brackets', 1)
    n = len(v.tests)
    ok = feedback.rules_feedback(v, 'python', 'print(1)', _result('OK', ['OK'] * n))
    assert ok['source'] == 'rules' and 'Все' in ok['summary']
    wa = feedback.rules_feedback(v, 'python', 'print(1)', _result('WA', ['WA'] + ['OK'] * (n - 1)))
    assert 'пример из условия' in wa['summary'] and any('формат вывода' in p for p in wa['points'])
    tle = feedback.rules_feedback(v, 'javascript', '', _result('TLE', ['OK', 'OK', 'TLE']))
    assert any('сложность' in p for p in tle['points'])
    mle = feedback.rules_feedback(v, 'python', '', _result('MLE', ['OK', 'OK', 'MLE']))
    assert any('копии' in p for p in mle['points'])
    re_ = _result('RE', ['RE'])
    re_.message = 'Traceback\nZeroDivisionError: division by zero'
    assert any('ZeroDivisionError' in p for p in feedback.rules_feedback(v, 'python', '', re_)['points'])
    ce = feedback.rules_feedback(v, 'python', 'def (', _result('CE', []))
    assert 'синтаксическая' in ce['summary']


class _FakeLLM:
    def __init__(self, data: Any = None, fail: bool = False) -> None:
        self.data, self.fail, self.calls = data, fail, 0

    @property
    def is_configured(self) -> bool:
        return True

    async def complete_json(self, *, system: str, user: str) -> Any:
        self.calls += 1
        assert 'вердикт не меняй' in system and 'Код:' in user
        if self.fail:
            raise RuntimeError('timeout')
        return self.data


async def test_review_uses_gigachat_and_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    v = variant('sum-multiples', 7)
    res = _result('WA', ['OK', 'OK', 'WA'])
    llm = _FakeLLM({'summary': 'Переполнение не при чём, ошибка в границе.', 'points': ['Проверьте n = 0']})
    monkeypatch.setattr(feedback, 'get_llm', lambda: llm)
    out = await feedback.review(v, 'python', 'print(0)', res)
    assert out['source'] == 'gigachat' and out['points'] == ['Проверьте n = 0']

    monkeypatch.setattr(feedback, 'get_llm', lambda: _FakeLLM(fail=True))
    assert (await feedback.review(v, 'python', 'print(0)', res))['source'] == 'rules'

    empty = _FakeLLM({'summary': ''})
    monkeypatch.setattr(feedback, 'get_llm', lambda: empty)
    assert (await feedback.review(v, 'python', 'print(0)', res))['source'] == 'rules'

    ce = _FakeLLM({'summary': 'x'})
    monkeypatch.setattr(feedback, 'get_llm', lambda: ce)
    await feedback.review(v, 'python', 'def (', _result('CE', []))
    assert ce.calls == 0
