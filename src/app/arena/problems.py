"""Банк задач Arena: варианты по зерну, тесты и эталонные решения.

Задача задаётся чистыми функциями: параметры варианта по зерну, условие,
генератор входов, эталонная функция ответа и эталонный код (тот же алгоритм
отдельной программой: CI прогоняет его через песочницу на всех тестах).
Зерно зависит от раунда, участника и задачи, поэтому у участников разные
данные и примеры при одинаковой идее и сложности.
"""

from __future__ import annotations

import functools
import hashlib
import heapq
import random
from collections import Counter, OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.arena.judge import TestCase

# Рейтинг задачи как соперника в Glicko-2 (см. rating.py): по уровню.
LEVEL_RATING = {1: 1200.0, 2: 1500.0, 3: 1800.0}
LEVEL_TITLES = {1: 'Лёгкая', 2: 'Средняя', 3: 'Сложная'}


@dataclass(frozen=True)
class Problem:
    code: str
    title: str
    level: int
    topic: str
    complexity: str  # ожидаемая сложность эталона
    idea: str  # ключевая идея для разбора
    params: Callable[[random.Random], dict[str, Any]]
    statement: Callable[[dict[str, Any]], str]
    inputs: Callable[[dict[str, Any], random.Random], list[str]]  # первые два — примеры
    solve: Callable[[dict[str, Any], str], str]
    reference: Callable[[dict[str, Any]], str]
    pitfalls: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class Variant:
    problem: Problem
    seed: int
    params: dict[str, Any]
    statement: str
    tests: list[TestCase]

    @property
    def samples(self) -> list[TestCase]:
        return [t for t in self.tests if t.sample]


def _ints(rng: random.Random, n: int, lo: int, hi: int) -> str:
    return ' '.join(str(rng.randint(lo, hi)) for _ in range(n))


# ── 1. Кратные K ─────────────────────────────────────────────────────────────
def _mult_inputs(p: dict, rng: random.Random) -> list[str]:
    k = p['k']
    out = []
    for n, lo, hi in [
        (6, -20, 40),
        (5, 1, 30),
        (1, 1, 9),
        (8, -100, 100),
        (10, -(10**9), 10**9),
        (1, k, k),
        (50, -1000, 1000),
    ]:
        out.append(f'{n}\n{_ints(rng, n, lo, hi)}\n')
    out.append(f'3\n{k * 7} {-k * 3} {k + 1}\n')
    out.append(f'200000\n{_ints(rng, 200000, -(10**9), 10**9)}\n')
    return out


def _mult_solve(p: dict, data: str) -> str:
    nums = list(map(int, data.split()))[1:]
    return str(sum(x for x in nums if x % p['k'] == 0))


MULTIPLES = Problem(
    code='sum-multiples',
    title='Сумма кратных',
    level=1,
    topic='Массивы',
    complexity='O(n)',
    idea='Один проход по массиву, проверка остатка от деления и накопление суммы в целом числе без переполнения.',
    params=lambda rng: {'k': rng.randint(3, 9)},
    statement=lambda p: (
        f'Сервис метрик присылает **n** целых чисел. Выведите сумму тех из них, которые делятся на **{p["k"]}** без остатка.\n\n'
        '**Ввод.** В первой строке n (1 ≤ n ≤ 2·10⁵). Во второй — n целых чисел, по модулю не больше 10⁹.\n\n'
        f'**Вывод.** Одно число — сумма чисел, кратных {p["k"]}. Если таких нет, выведите 0.'
    ),
    inputs=_mult_inputs,
    solve=_mult_solve,
    reference=lambda p: (
        'import sys\n'
        'data = sys.stdin.buffer.read().split()\n'
        'n = int(data[0])\n'
        f'print(sum(x for x in map(int, data[1:n + 1]) if x % {p["k"]} == 0))\n'
    ),
    pitfalls=('отрицательные числа тоже бывают кратными', 'сумма может выйти за 32 бита'),
)


# ── 2. Самый частый код ответа ───────────────────────────────────────────────
STATUSES = [200, 201, 204, 301, 302, 400, 401, 403, 404, 409, 429, 500, 502, 503]


def _status_inputs(p: dict, rng: random.Random) -> list[str]:
    out = []
    for n in (7, 6, 1, 12, 30, 100, 2):
        out.append(f'{n}\n' + ' '.join(str(rng.choice(STATUSES)) for _ in range(n)) + '\n')
    tie = rng.sample(STATUSES, 3)
    out.append('6\n' + ' '.join(map(str, [tie[0], tie[1], tie[2], tie[2], tie[1], tie[0]])) + '\n')
    out.append('200000\n' + ' '.join(str(rng.choice(STATUSES)) for _ in range(200000)) + '\n')
    return out


def _status_solve(p: dict, data: str) -> str:
    codes = list(map(int, data.split()))[1:]
    cnt = Counter(codes)
    best = max(cnt.values())
    pick = min if p['tie'] == 'min' else max
    return str(pick(c for c, v in cnt.items() if v == best))


TOP_STATUS = Problem(
    code='top-status',
    title='Самый частый код ответа',
    level=1,
    topic='Хеш-таблицы',
    complexity='O(n)',
    idea='Подсчитать частоты словарём за один проход, затем выбрать максимум с правилом для равенства.',
    params=lambda rng: {'tie': rng.choice(['min', 'max'])},
    statement=lambda p: (
        'В журнале веб-сервера записаны HTTP-коды ответов. Найдите код, который встречается чаще всего. '
        f'Если таких кодов несколько, выведите **{"наименьший" if p["tie"] == "min" else "наибольший"}** из них.\n\n'
        '**Ввод.** В первой строке n (1 ≤ n ≤ 2·10⁵). Во второй — n кодов ответа.\n\n'
        '**Вывод.** Один код.'
    ),
    inputs=_status_inputs,
    solve=_status_solve,
    reference=lambda p: (
        'import sys\n'
        'from collections import Counter\n'
        'data = sys.stdin.buffer.read().split()\n'
        'n = int(data[0])\n'
        'cnt = Counter(map(int, data[1:n + 1]))\n'
        'best = max(cnt.values())\n'
        f'print({"min" if p["tie"] == "min" else "max"}(c for c, v in cnt.items() if v == best))\n'
    ),
    pitfalls=('правило выбора при равных частотах',),
)


# ── 3. Логины-палиндромы ─────────────────────────────────────────────────────
ALPHA = 'abcABC'


def _login(rng: random.Random, pal: bool) -> str:
    n = rng.randint(1, 8)
    half = ''.join(rng.choice(ALPHA) for _ in range(n))
    if not pal:
        return half + rng.choice('xyz') + half[::-1] + rng.choice('pq')
    mid = rng.choice(['', rng.choice(ALPHA)])
    tail = ''.join(c.swapcase() if rng.random() < 0.5 else c for c in half[::-1])
    return half + mid + tail


def _pal_inputs(p: dict, rng: random.Random) -> list[str]:
    out = []
    for n in (6, 5, 1, 10, 40, 3):
        words = [_login(rng, rng.random() < 0.5) for _ in range(n)]
        out.append(f'{n}\n' + '\n'.join(words) + '\n')
    out.append('4\na\nAa\naBa\nxY\n')
    out.append('3\nAbBa\nabcCBA\nQ\n')
    out.append('50000\n' + '\n'.join(_login(rng, rng.random() < 0.5) for _ in range(50000)) + '\n')
    return out


def _pal_solve(p: dict, data: str) -> str:
    words = data.split()[1:]
    return str(sum(1 for w in words if len(w) >= p['min_len'] and w.lower() == w.lower()[::-1]))


PALINDROMES = Problem(
    code='palindromes',
    title='Логины-палиндромы',
    level=1,
    topic='Строки',
    complexity='O(суммарной длины)',
    idea='Привести строку к одному регистру и сравнить с развёрнутой; не забыть ограничение на длину.',
    params=lambda rng: {'min_len': rng.randint(2, 4)},
    statement=lambda p: (
        'Служба безопасности ищет логины, которые читаются одинаково слева направо и справа налево '
        f'без учёта регистра букв. Посчитайте такие логины длиной **не меньше {p["min_len"]}**.\n\n'
        '**Ввод.** В первой строке n (1 ≤ n ≤ 5·10⁴), далее n строк — логины из латинских букв.\n\n'
        '**Вывод.** Одно число.'
    ),
    inputs=_pal_inputs,
    solve=_pal_solve,
    reference=lambda p: (
        'import sys\n'
        'words = sys.stdin.read().split()[1:]\n'
        f'print(sum(1 for w in words if len(w) >= {p["min_len"]} and w.lower() == w.lower()[::-1]))\n'
    ),
    pitfalls=('регистр букв', 'минимальная длина'),
)


# ── 4. Пиковая нагрузка (скользящее окно) ────────────────────────────────────
def _window_inputs(p: dict, rng: random.Random) -> list[str]:
    out = []
    for n, w in [(7, 3), (5, 2), (1, 1), (6, 6), (20, 4), (100, 17)]:
        out.append(f'{n} {w}\n{_ints(rng, n, -50, 100)}\n')
    out.append(f'5 1\n{_ints(rng, 5, -9, 9)}\n')
    n = 200000
    out.append(f'{n} {n // 2}\n{_ints(rng, n, -(10**4), 10**4)}\n')
    out.append(f'{n} 1000\n{_ints(rng, n, 0, 10**4)}\n')
    return out


def _window_solve(p: dict, data: str) -> str:
    nums = list(map(int, data.split()))
    n, w, a = nums[0], nums[1], nums[2:]
    cur = sum(a[:w])
    best = cur
    pick = max if p['mode'] == 'max' else min
    for i in range(w, n):
        cur += a[i] - a[i - w]
        best = pick(best, cur)
    return str(best)


LOAD_WINDOW = Problem(
    code='load-window',
    title='Пиковая нагрузка',
    level=2,
    topic='Два указателя',
    complexity='O(n)',
    idea='Скользящее окно: при сдвиге прибавить входящий элемент и вычесть выходящий, а не пересчитывать сумму окна заново.',
    params=lambda rng: {'mode': rng.choice(['max', 'min'])},
    statement=lambda p: (
        'Мониторинг записал число запросов в каждую из n секунд (значение может быть отрицательным после коррекции). '
        f'Найдите **{"наибольшую" if p["mode"] == "max" else "наименьшую"}** суммарную нагрузку за любые w подряд идущих секунд.\n\n'
        '**Ввод.** В первой строке n и w (1 ≤ w ≤ n ≤ 2·10⁵). Во второй — n целых чисел, по модулю не больше 10⁴.\n\n'
        '**Вывод.** Одно число.'
    ),
    inputs=_window_inputs,
    solve=_window_solve,
    reference=lambda p: (
        'import sys\n'
        'data = sys.stdin.buffer.read().split()\n'
        'n, w = int(data[0]), int(data[1])\n'
        'a = list(map(int, data[2:2 + n]))\n'
        'cur = sum(a[:w])\n'
        'best = cur\n'
        'for i in range(w, n):\n'
        '    cur += a[i] - a[i - w]\n'
        f'    if cur {">" if p["mode"] == "max" else "<"} best:\n'
        '        best = cur\n'
        'print(best)\n'
    ),
    pitfalls=('пересчёт суммы окна заново даёт O(n·w) и превышение времени', 'w может быть равно n'),
)


# ── 5. Скобки в конфиге ──────────────────────────────────────────────────────
BRACKET_SETS = {'round-square': '()[]', 'round-curly': '(){}', 'all': '()[]{}'}


def _brackets_line(rng: random.Random, pairs: str, n: int, balanced: bool) -> str:
    opens, closes = pairs[0::2], pairs[1::2]
    stack: list[int] = []
    out = []
    for _ in range(n):
        if stack and (rng.random() < 0.5):
            out.append(closes[stack.pop()])
        else:
            k = rng.randrange(len(opens))
            stack.append(k)
            out.append(opens[k])
    while stack:
        out.append(closes[stack.pop()])
    s = ''.join(out)
    if not balanced and s:
        i = rng.randrange(len(s))
        s = s[:i] + rng.choice(pairs) + s[i + 1 :]
        if rng.random() < 0.3:
            s = s[1:]
    return s


def _brackets_inputs(p: dict, rng: random.Random) -> list[str]:
    pairs = BRACKET_SETS[p['set']]
    out = []
    for q, n in [(4, 4), (3, 3), (1, 1), (6, 8), (10, 20), (20, 50)]:
        lines = [_brackets_line(rng, pairs, rng.randint(1, n), rng.random() < 0.5) for _ in range(q)]
        out.append(f'{q}\n' + '\n'.join(lines) + '\n')
    out.append(f'3\n{pairs[1]}\n{pairs[0]}\n{pairs[0]}{pairs[3]}{pairs[2]}{pairs[1]}\n')
    big = [_brackets_line(rng, pairs, 50000, i % 2 == 0) for i in range(4)]
    out.append('4\n' + '\n'.join(big) + '\n')
    return out


def _brackets_ok(s: str, pairs: str) -> bool:
    match = {pairs[i + 1]: pairs[i] for i in range(0, len(pairs), 2)}
    stack: list[str] = []
    for ch in s:
        if ch in match:
            if not stack or stack.pop() != match[ch]:
                return False
        else:
            stack.append(ch)
    return not stack


def _brackets_solve(p: dict, data: str) -> str:
    lines = data.split()[1:]
    return '\n'.join('YES' if _brackets_ok(s, BRACKET_SETS[p['set']]) else 'NO' for s in lines)


BRACKETS = Problem(
    code='brackets',
    title='Скобки в конфиге',
    level=2,
    topic='Стек',
    complexity='O(длины строки)',
    idea='Стек открывающих скобок: закрывающая должна совпасть по типу с вершиной стека; в конце стек пуст.',
    params=lambda rng: {'set': rng.choice(list(BRACKET_SETS))},
    statement=lambda p: (
        f'Шаблонизатор конфигов использует скобки `{" ".join(BRACKET_SETS[p["set"]])}`. '
        'Для каждой строки определите, правильная ли в ней скобочная последовательность: '
        'каждая открывающая скобка закрыта скобкой того же типа, и пары не пересекаются.\n\n'
        '**Ввод.** В первой строке q (1 ≤ q ≤ 20). Далее q непустых строк из этих скобок, суммарная длина не больше 2·10⁵.\n\n'
        '**Вывод.** Для каждой строки YES или NO.'
    ),
    inputs=_brackets_inputs,
    solve=_brackets_solve,
    reference=lambda p: (
        'import sys\n'
        f'PAIRS = {BRACKET_SETS[p["set"]]!r}\n'
        'match = {PAIRS[i + 1]: PAIRS[i] for i in range(0, len(PAIRS), 2)}\n'
        'def ok(s):\n'
        '    st = []\n'
        '    for ch in s:\n'
        '        if ch in match:\n'
        '            if not st or st.pop() != match[ch]:\n'
        '                return False\n'
        '        else:\n'
        '            st.append(ch)\n'
        '    return not st\n'
        'lines = sys.stdin.read().split()[1:]\n'
        "print('\\n'.join('YES' if ok(s) else 'NO' for s in lines))\n"
    ),
    pitfalls=(
        'закрывающая скобка при пустом стеке',
        'незакрытые скобки в конце строки',
        'подсчёт без стека не различает типы',
    ),
)


# ── 6. Промахи LRU-кэша ──────────────────────────────────────────────────────
def _lru_inputs(p: dict, rng: random.Random) -> list[str]:
    out = []
    for c, n, keys in [(2, 7, 4), (3, 6, 5), (1, 1, 1), (2, 10, 3), (4, 30, 8), (5, 100, 20), (1, 8, 2)]:
        out.append(f'{c} {n}\n{_ints(rng, n, 1, keys)}\n')
    out.append('3 6\n1 2 3 1 4 2\n')
    out.append(f'1000 200000\n{_ints(rng, 200000, 1, 3000)}\n')
    return out


def _lru_solve(p: dict, data: str) -> str:
    nums = list(map(int, data.split()))
    cap, n, keys = nums[0], nums[1], nums[2:]
    cache: OrderedDict[int, None] = OrderedDict()
    hits = misses = 0
    for k in keys[:n]:
        if k in cache:
            hits += 1
            cache.move_to_end(k)
        else:
            misses += 1
            cache[k] = None
            if len(cache) > cap:
                cache.popitem(last=False)
    return str(hits if p['count'] == 'hits' else misses)


LRU = Problem(
    code='lru-cache',
    title='LRU-кэш',
    level=2,
    topic='Структуры данных',
    complexity='O(n)',
    idea='Упорядоченный словарь (или словарь + двусвязный список): попадание переносит ключ в конец, вытесняется самый давний.',
    params=lambda rng: {'count': rng.choice(['hits', 'misses'])},
    statement=lambda p: (
        'Кэш вмещает c ключей и вытесняет ключ, к которому дольше всего не обращались (LRU). '
        'Изначально кэш пуст. По последовательности обращений посчитайте число '
        f'**{"попаданий (ключ уже был в кэше)" if p["count"] == "hits" else "промахов (ключа не было в кэше)"}**.\n\n'
        '**Ввод.** В первой строке c и n (1 ≤ c ≤ 10⁴, 1 ≤ n ≤ 2·10⁵). Во второй — n ключей, целые от 1 до 10⁹.\n\n'
        '**Вывод.** Одно число.'
    ),
    inputs=_lru_inputs,
    solve=_lru_solve,
    reference=lambda p: (
        'import sys\n'
        'from collections import OrderedDict\n'
        'data = sys.stdin.buffer.read().split()\n'
        'cap, n = int(data[0]), int(data[1])\n'
        'cache = OrderedDict()\n'
        'hits = misses = 0\n'
        'for k in data[2:2 + n]:\n'
        '    if k in cache:\n'
        '        hits += 1\n'
        '        cache.move_to_end(k)\n'
        '    else:\n'
        '        misses += 1\n'
        '        cache[k] = None\n'
        '        if len(cache) > cap:\n'
        '            cache.popitem(last=False)\n'
        f'print({p["count"]})\n'
    ),
    pitfalls=('попадание обновляет «свежесть» ключа', 'поиск по списку даёт O(n·c)'),
)


# ── 7. Маршрут деплоя (Дейкстра) ─────────────────────────────────────────────
def _graph(rng: random.Random, n: int, m: int, wmax: int) -> list[tuple[int, int, int]]:
    edges = []
    for _ in range(m):
        u, v = rng.randint(1, n), rng.randint(1, n)
        edges.append((u, v, rng.randint(1, wmax)))
    return edges


def _route_input(n: int, edges: list[tuple[int, int, int]]) -> str:
    return f'{n} {len(edges)}\n' + '\n'.join(f'{u} {v} {w}' for u, v, w in edges) + '\n'


def _route_inputs(p: dict, rng: random.Random) -> list[str]:
    out = [_route_input(n, _graph(rng, n, m, 20)) for n, m in [(5, 7), (4, 4), (6, 12), (30, 80), (200, 600)]]
    out.append('1 0\n')
    out.append('3 1\n2 3 5\n')
    chain = [(i, i + 1, 10**4) for i in range(1, 50000)]
    out.append(_route_input(50000, chain))
    out.append(_route_input(40000, _graph(rng, 40000, 120000, 10**4)))
    return out


def _route_solve(p: dict, data: str) -> str:
    nums = list(map(int, data.split()))
    n, m = nums[0], nums[1]
    adj: list[list[tuple[int, int]]] = [[] for _ in range(n + 1)]
    for i in range(m):
        u, v, w = nums[2 + 3 * i : 5 + 3 * i]
        adj[u].append((v, w))
        if not p['directed']:
            adj[v].append((u, w))
    dist = [-1] * (n + 1)
    heap = [(0, 1)]
    while heap:
        d, u = heapq.heappop(heap)
        if dist[u] != -1:
            continue
        dist[u] = d
        for v, w in adj[u]:
            if dist[v] == -1:
                heapq.heappush(heap, (d + w, v))
    return str(dist[n])


ROUTE = Problem(
    code='deploy-route',
    title='Маршрут деплоя',
    level=3,
    topic='Графы',
    complexity='O((n + m) log n)',
    idea='Алгоритм Дейкстры с кучей: веса положительные, поэтому первый раз извлечённое из кучи расстояние окончательное.',
    params=lambda rng: {'directed': rng.choice([True, False])},
    statement=lambda p: (
        'Артефакт сборки нужно доставить от узла 1 до узла n. Между узлами есть '
        f'{"однонаправленные каналы u → v" if p["directed"] else "двусторонние каналы u — v"} '
        'со временем передачи w. Найдите минимальное время доставки или выведите -1, если узел n недостижим.\n\n'
        '**Ввод.** В первой строке n и m (1 ≤ n ≤ 5·10⁴, 0 ≤ m ≤ 1,2·10⁵). Далее m строк: u v w (1 ≤ w ≤ 10⁴). '
        'Возможны петли и кратные каналы.\n\n'
        '**Вывод.** Одно число.'
    ),
    inputs=_route_inputs,
    solve=_route_solve,
    reference=lambda p: (
        'import sys, heapq\n'
        'data = sys.stdin.buffer.read().split()\n'
        'n, m = int(data[0]), int(data[1])\n'
        'adj = [[] for _ in range(n + 1)]\n'
        'for i in range(m):\n'
        '    u, v, w = int(data[2 + 3 * i]), int(data[3 + 3 * i]), int(data[4 + 3 * i])\n'
        '    adj[u].append((v, w))\n'
        + ('' if p['directed'] else '    adj[v].append((u, w))\n')
        + 'INF = float("inf")\n'
        'dist = [INF] * (n + 1)\n'
        'dist[1] = 0\n'
        'heap = [(0, 1)]\n'
        'while heap:\n'
        '    d, u = heapq.heappop(heap)\n'
        '    if d > dist[u]:\n'
        '        continue\n'
        '    for v, w in adj[u]:\n'
        '        if d + w < dist[v]:\n'
        '            dist[v] = d + w\n'
        '            heapq.heappush(heap, (d + w, v))\n'
        'print(dist[n] if dist[n] < INF else -1)\n'
    ),
    pitfalls=('недостижимый узел', 'n = 1', 'обход в ширину не учитывает веса', 'Дейкстра без кучи даёт O(n²)'),
)


# ── 8. Порядок задач (топологическая сортировка) ─────────────────────────────
def _dag(rng: random.Random, n: int, m: int, cyclic: bool) -> list[tuple[int, int]]:
    order = list(range(1, n + 1))
    rng.shuffle(order)
    edges = []
    for _ in range(m):
        i, j = sorted(rng.sample(range(n), 2)) if n > 1 else (0, 0)
        if i != j:
            edges.append((order[i], order[j]))
    if cyclic and n > 1:
        edges.append((order[-1], order[0]))
    return edges


def _order_input(n: int, edges: list[tuple[int, int]]) -> str:
    return f'{n} {len(edges)}\n' + '\n'.join(f'{a} {b}' for a, b in edges) + '\n'


def _order_inputs(p: dict, rng: random.Random) -> list[str]:
    out = [
        _order_input(n, _dag(rng, n, m, cyc))
        for n, m, cyc in [(5, 4, False), (4, 4, True), (6, 5, False), (8, 12, False), (30, 60, True), (300, 900, False)]
    ]
    out.append('1 0\n')
    out.append('3 0\n')
    out.append(_order_input(50000, _dag(rng, 50000, 100000, False)))
    return out


def _order_solve(p: dict, data: str) -> str:
    nums = list(map(int, data.split()))
    n, m = nums[0], nums[1]
    adj: list[list[int]] = [[] for _ in range(n + 1)]
    indeg = [0] * (n + 1)
    for i in range(m):
        a, b = nums[2 + 2 * i], nums[3 + 2 * i]
        adj[a].append(b)
        indeg[b] += 1
    sign = 1 if p['pick'] == 'min' else -1
    heap = [sign * v for v in range(1, n + 1) if indeg[v] == 0]
    heapq.heapify(heap)
    res = []
    while heap:
        v = sign * heapq.heappop(heap)
        res.append(v)
        for u in adj[v]:
            indeg[u] -= 1
            if indeg[u] == 0:
                heapq.heappush(heap, sign * u)
    return ' '.join(map(str, res)) if len(res) == n else '-1'


TASK_ORDER = Problem(
    code='task-order',
    title='Порядок задач',
    level=3,
    topic='Графы',
    complexity='O((n + m) log n)',
    idea='Алгоритм Кана с кучей вместо очереди: из доступных задач всегда берётся нужная по номеру; если обработаны не все — есть цикл.',
    params=lambda rng: {'pick': rng.choice(['min', 'max'])},
    statement=lambda p: (
        'В пайплайне n задач и m зависимостей «a должна выполниться раньше b». Выведите порядок выполнения всех задач, '
        f'в котором из доступных в каждый момент задач берётся задача с **{"наименьшим" if p["pick"] == "min" else "наибольшим"}** номером. '
        'Если зависимости содержат цикл, выведите -1.\n\n'
        '**Ввод.** В первой строке n и m (1 ≤ n ≤ 5·10⁴, 0 ≤ m ≤ 10⁵). Далее m строк: a b.\n\n'
        '**Вывод.** n номеров через пробел или -1.'
    ),
    inputs=_order_inputs,
    solve=_order_solve,
    reference=lambda p: (
        'import sys, heapq\n'
        'data = sys.stdin.buffer.read().split()\n'
        'n, m = int(data[0]), int(data[1])\n'
        'adj = [[] for _ in range(n + 1)]\n'
        'indeg = [0] * (n + 1)\n'
        'for i in range(m):\n'
        '    a, b = int(data[2 + 2 * i]), int(data[3 + 2 * i])\n'
        '    adj[a].append(b)\n'
        '    indeg[b] += 1\n'
        f'sign = {1 if p["pick"] == "min" else -1}\n'
        'heap = [sign * v for v in range(1, n + 1) if indeg[v] == 0]\n'
        'heapq.heapify(heap)\n'
        'res = []\n'
        'while heap:\n'
        '    v = sign * heapq.heappop(heap)\n'
        '    res.append(v)\n'
        '    for u in adj[v]:\n'
        '        indeg[u] -= 1\n'
        '        if indeg[u] == 0:\n'
        '            heapq.heappush(heap, sign * u)\n'
        "print(' '.join(map(str, res)) if len(res) == n else -1)\n"
    ),
    pitfalls=('цикл в зависимостях', 'обычная очередь не даёт нужный порядок', 'задачи без зависимостей'),
)


PROBLEMS: dict[str, Problem] = {
    p.code: p for p in (MULTIPLES, TOP_STATUS, PALINDROMES, LOAD_WINDOW, BRACKETS, LRU, ROUTE, TASK_ORDER)
}
OPEN_ROUND_PROBLEMS = ['sum-multiples', 'brackets', 'load-window', 'deploy-route']


def variant_seed(*parts: Any) -> int:
    digest = hashlib.sha256(':'.join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:8], 'big')


@functools.lru_cache(maxsize=32)
def variant(code: str, seed: int) -> Variant:
    problem = PROBLEMS[code]
    rng = random.Random(seed)
    params = problem.params(rng)
    inputs = problem.inputs(params, rng)
    tests = [TestCase(input=i, expected=problem.solve(params, i) + '\n', sample=k < 2) for k, i in enumerate(inputs)]
    return Variant(problem=problem, seed=seed, params=params, statement=problem.statement(params), tests=tests)


def public(v: Variant) -> dict[str, Any]:
    p = v.problem
    return {
        'code': p.code,
        'title': p.title,
        'level': p.level,
        'level_title': LEVEL_TITLES[p.level],
        'topic': p.topic,
        'statement': v.statement,
        'samples': [{'input': t.input, 'output': t.expected} for t in v.samples],
        'tests_total': len(v.tests),
    }


def catalog() -> list[dict[str, Any]]:
    return [catalog_item(c) for c in PROBLEMS]


def catalog_item(code: str) -> dict[str, Any]:
    p = PROBLEMS[code]
    return {'code': p.code, 'title': p.title, 'level': p.level, 'level_title': LEVEL_TITLES[p.level], 'topic': p.topic}
