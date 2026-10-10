"""Банк задач Arena (FSP-39): эталоны проходят тесты, варианты различаются."""

from __future__ import annotations

import pytest

from app.arena import problems
from app.arena.judge import judge_sync


@pytest.mark.parametrize('code', list(problems.PROBLEMS))
def test_reference_passes_all_generated_tests(code: str) -> None:
    for seed in (11, 12):
        v = problems.variant(code, seed)
        assert len(v.samples) == 2
        r = judge_sync('python', v.problem.reference(v.params), v.tests)
        assert r.verdict == 'OK', (code, seed, [(t.verdict, t.message) for t in r.tests if t.verdict != 'OK'])


def test_participants_get_different_variants() -> None:
    for code in problems.PROBLEMS:
        a = problems.variant(code, problems.variant_seed('round', 'alice', code))
        b = problems.variant(code, problems.variant_seed('round', 'bob', code))
        assert a.problem.idea == b.problem.idea
        assert [t.input for t in a.tests] != [t.input for t in b.tests]


def test_slow_solution_gets_tle() -> None:
    v = problems.variant('load-window', 5)
    naive = (
        'n, w = map(int, input().split())\n'
        'a = list(map(int, input().split()))\n'
        'print(max(sum(a[i:i + w]) for i in range(n - w + 1)))\n'
    )
    r = judge_sync('python', naive, v.tests)
    assert r.verdict in ('TLE', 'WA')
    assert r.passed < r.total
