"""Рейтинг Arena (FSP-42): Glicko-2 и антисписывание."""

from __future__ import annotations

from app.arena import rating, similarity


def test_glickman_reference_example() -> None:
    p = rating.Player(1500, 200, 0.06)
    out = rating.update(p, [(1400, 30, 1), (1550, 100, 0), (1700, 300, 0)])
    assert abs(out.rating - 1464.06) < 0.1
    assert abs(out.rd - 151.52) < 0.1


def test_wins_raise_rating_and_reduce_uncertainty() -> None:
    p = rating.Player()
    assert p.provisional
    for _ in range(6):
        p = rating.update(p, [(1200, 50, 1), (1500, 50, 1), (1500, 50, 1), (1800, 50, 0)])
    assert p.rating > 1600
    assert not p.provisional
    worse = rating.update(p, [(1200, 50, 0), (1500, 50, 0)])
    assert worse.rating < p.rating


def test_inactivity_grows_uncertainty() -> None:
    p = rating.Player(1700, 60, 0.06)
    assert rating.inflate(p, 10).rd == 60
    assert rating.inflate(p, 400).rd > 60


def test_matching_score_scale() -> None:
    assert rating.matching_score(None, None) == 0
    assert rating.matching_score(2000, 50) == 100
    assert rating.matching_score(1600, 300) == 25


CODE_A = """
import sys
data = sys.stdin.read().split()
n = int(data[0])
total = 0
for x in data[1:n + 1]:
    v = int(x)
    if v % 3 == 0:
        total += v
print(total)
"""
CODE_B = """
import sys
# переименованные переменные и комментарии
tokens = sys.stdin.read().split()
count = int(tokens[0])
acc = 0
for item in tokens[1:count + 1]:
    num = int(item)
    if num % 7 == 0:
        acc += num   # сумма
print(acc)
"""
CODE_C = """
import sys
nums = list(map(int, sys.stdin.read().split()))[1:]
print(sum(filter(lambda q: q % 3 == 0, nums)))
"""


def test_renamed_copy_is_suspicious() -> None:
    assert similarity.suspicious('python', CODE_A, CODE_B)
    assert not similarity.suspicious('python', CODE_A, CODE_C)
