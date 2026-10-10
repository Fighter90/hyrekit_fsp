"""Банк параметрических заданий.

Ключевая идея устойчивости к утечкам: в банке хранятся не готовые вопросы,
а *семейства* заданий — генераторы, которые по зерну (seed) порождают
конкретный вариант: другие числа, имена, данные, порядок вариантов ответа.
Правильный ответ вычисляется кодом, поэтому «слитый» ответ одного кандидата
бесполезен другому. При этом сложность семейства задаётся параметром
`level` (1..5) и откалибрована заранее, поэтому разные кандидаты получают
задания сопоставимой сложности (см. engine.py, blueprint).

Семейства делятся на два класса:

* генеративные — ответ вычисляется из случайных данных (код, числа, таблицы),
  пространство вариантов практически бесконечно, выученный ответ не переносится;
* концептуальные (`conceptual=True`) — проверяют знание понятия с конечным
  набором формулировок. Их ответы со временем расходятся по рынку, поэтому в
  плане попытки первое задание каждой темы всегда генеративное, а доля
  концептуальных ограничена (engine.MAX_CONCEPTUAL). Экспозицию каждого
  семейства считает scripts/validate.py.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Kind = str  # 'single' | 'multi' | 'number'


@dataclass(frozen=True)
class Item:
    """Конкретный вариант задания."""

    family: str
    topic: str
    level: int
    kind: Kind
    stem: str
    answer: Any  # индекс варианта (single), отсортированный список индексов (multi), число
    options: list[str] = field(default_factory=list)
    code: str | None = None


Generator = Callable[[random.Random, int], Item]
FAMILIES: dict[str, tuple[str, Generator]] = {}


MIN_LEVEL: dict[str, int] = {}
CONCEPTUAL: set[str] = set()


def family(name: str, topic: str, *, min_level: int = 1, conceptual: bool = False) -> Callable[[Generator], Generator]:
    """Регистрация семейства. min_level — с какого уровня сложности семейство осмысленно."""

    def deco(fn: Generator) -> Generator:
        FAMILIES[name] = (topic, fn)
        MIN_LEVEL[name] = min_level
        if conceptual:
            CONCEPTUAL.add(name)
        return fn

    return deco


def _single(
    rng: random.Random,
    name: str,
    topic: str,
    level: int,
    stem: str,
    correct: Any,
    distractors: list[Any],
    code: str | None = None,
) -> Item:
    """Собирает вопрос с одним ответом и перемешанными вариантами."""
    opts: list[str] = []
    for value in [correct, *distractors]:
        text = str(value)
        if text not in opts:
            opts.append(text)
    rng.shuffle(opts)
    return Item(name, topic, level, 'single', stem, opts.index(str(correct)), opts, code)


def _near(rng: random.Random, value: int, count: int = 3, spread: int = 3) -> list[int]:
    out: set[int] = set()
    while len(out) < count:
        d = rng.randint(-spread, spread) or 1
        if value + d != value:
            out.add(value + d)
    return list(out)


NAMES = ['alice', 'boris', 'vera', 'gleb', 'dina', 'egor', 'zoya', 'ivan', 'kira', 'lev', 'mila', 'nik']
CITIES = ['Казань', 'Пермь', 'Томск', 'Самара', 'Тула', 'Омск', 'Сочи', 'Уфа']


# ── algorithms ────────────────────────────────────────────────────────────────
@family('algo_binary_steps', 'algorithms')
def algo_binary_steps(rng: random.Random, level: int) -> Item:
    n = rng.randint(2 ** (3 + level * 2), 2 ** (6 + level * 3))
    steps = n.bit_length()  # худший случай без ключа: floor(log2 n) + 1 сравнений
    stem = (
        f'Отсортированный массив содержит {n} элементов. Какое максимальное число сравнений '
        'с искомым ключом сделает бинарный поиск, если ключа в массиве нет?'
    )
    return _single(rng, 'algo_binary_steps', 'algorithms', level, stem, steps, _near(rng, steps))


@family('algo_complexity', 'algorithms', conceptual=True)
def algo_complexity(rng: random.Random, level: int) -> Item:
    variants = [
        ('for i in range(n):\n    for j in range(i, n):\n        total += a[i] * a[j]', 'O(n²)'),
        ('i = n\nwhile i > 1:\n    i //= 2\n    ops += 1', 'O(log n)'),
        ('for i in range(n):\n    j = 1\n    while j < n:\n        j *= 2', 'O(n log n)'),
        ('def f(n):\n    if n <= 1:\n        return 1\n    return f(n - 1) + f(n - 1)', 'O(2ⁿ)'),
        ('seen = set()\nfor x in a:\n    if k - x in seen:\n        return True\n    seen.add(x)', 'O(n)'),
        ('for i in range(n):\n    for j in range(n):\n        for k in range(j):\n            c += 1', 'O(n³)'),
    ]
    pool = variants[: 2 + level] if level < 5 else variants
    code, ans = rng.choice(pool)
    all_opts = ['O(1)', 'O(log n)', 'O(n)', 'O(n log n)', 'O(n²)', 'O(n³)', 'O(2ⁿ)']
    distr = rng.sample([o for o in all_opts if o != ans], 3)
    return _single(
        rng,
        'algo_complexity',
        'algorithms',
        level,
        'Какова асимптотическая сложность фрагмента по времени?',
        ans,
        distr,
        code,
    )


@family('algo_stack_sim', 'algorithms')
def algo_stack_sim(rng: random.Random, level: int) -> Item:
    ops, stack = [], []
    for _ in range(3 + level * 2):
        if stack and rng.random() < 0.4:
            ops.append('pop')
            stack.pop()
        else:
            v = rng.randint(1, 9)
            ops.append(f'push {v}')
            stack.append(v)
    if not stack:
        v = rng.randint(1, 9)
        ops.append(f'push {v}')
        stack.append(v)
    ans = sum(stack)
    stem = 'Над пустым стеком выполнили операции. Чему равна сумма элементов, оставшихся в стеке?'
    return Item('algo_stack_sim', 'algorithms', level, 'number', stem, ans, [], '\n'.join(ops))


# ── python ────────────────────────────────────────────────────────────────────
@family('py_slice', 'python')
def py_slice(rng: random.Random, level: int) -> Item:
    data = rng.sample(range(10, 99), 6 + level)
    start = rng.randint(0, 2)
    stop = rng.randint(start + 2, len(data))
    step = rng.choice([1, 2] if level < 3 else [2, 3, -1])
    if step < 0:
        start, stop = stop - 1, start
    res = data[start:stop:step]
    code = f'a = {data}\nprint(a[{start}:{stop}:{step}])'
    distr = [data[start:stop], data[start + 1 : stop : step], res[::-1] if len(res) > 1 else data[:2]]
    return _single(rng, 'py_slice', 'python', level, 'Что выведет программа?', res, distr, code)


@family('py_mutable_default', 'python')
def py_mutable_default(rng: random.Random, level: int) -> Item:
    calls = rng.randint(2, 3 + level * 2)
    v = rng.randint(2, 60)
    fn, arg = rng.choice(['add', 'push', 'collect', 'keep']), rng.choice(['acc', 'items', 'buf', 'store'])
    code = (
        f'def {fn}(x, {arg}=[]):\n    {arg}.append(x)\n    return {arg}\n\n'
        f'for i in range({calls}):\n    r = {fn}(i * {v})\nprint(len(r), r[-1])'
    )
    ans = f'{calls} {(calls - 1) * v}'
    distr = [f'1 {(calls - 1) * v}', f'{calls} {calls * v}', f'1 {v}']
    return _single(rng, 'py_mutable_default', 'python', level, 'Что выведет программа?', ans, distr, code)


@family('py_dict_comp', 'python')
def py_dict_comp(rng: random.Random, level: int) -> Item:
    words = rng.sample(['кот', 'ёж', 'лиса', 'волк', 'бобр', 'енот', 'рысь', 'лось', 'сова'], 4 + level)
    k = rng.randint(2, 4)
    res = {w: len(w) for w in words if len(w) >= k}
    ans = sum(res.values())
    code = f'words = {words}\nd = {{w: len(w) for w in words if len(w) >= {k}}}\nprint(sum(d.values()))'
    return Item('py_dict_comp', 'python', level, 'number', 'Что выведет программа?', ans, [], code)


# ── javascript ───────────────────────────────────────────────────────────────
@family('js_event_loop', 'javascript', min_level=2)
def js_event_loop(rng: random.Random, level: int) -> Item:
    a, b, c, d = rng.sample(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'K', 'M', 'P', 'X'], 4)
    code = (
        f"console.log('{a}');\nsetTimeout(() => console.log('{b}'), 0);\n"
        f"Promise.resolve().then(() => console.log('{c}'));\nconsole.log('{d}');"
    )
    ans = f'{a} {d} {c} {b}'
    distr = [f'{a} {b} {c} {d}', f'{a} {d} {b} {c}', f'{a} {c} {d} {b}']
    return _single(
        rng,
        'js_event_loop',
        'javascript',
        level,
        'В каком порядке появятся строки в консоли?',
        ans,
        distr,
        code,
    )


@family('js_equality', 'javascript', conceptual=True)
def js_equality(rng: random.Random, level: int) -> Item:
    pairs = [
        ("0 == ''", True),
        ('null == undefined', True),
        ('null === undefined', False),
        ('NaN === NaN', False),
        ('[] == false', True),
        ("'5' + 1 === '51'", True),
        ("typeof null === 'object'", True),
        ("[1,2] == '1,2'", True),
        ('0.1 + 0.2 === 0.3', False),
    ]
    chosen = rng.sample(pairs, 4)
    opts = [p[0] for p in chosen]
    answer = sorted(i for i, p in enumerate(chosen) if p[1])
    if not answer:
        return js_equality(rng, level)
    return Item(
        'js_equality',
        'javascript',
        level,
        'multi',
        'Какие выражения JavaScript вернут true? Отметьте все.',
        answer,
        opts,
    )


@family('js_array_reduce', 'javascript')
def js_array_reduce(rng: random.Random, level: int) -> Item:
    arr = [rng.randint(1, 9) for _ in range(3 + level)]
    m = rng.randint(2, 3)
    ans = sum(x * m for x in arr if x % 2 == 0)
    code = f'const a = {arr};\nconst r = a.filter(x => x % 2 === 0).map(x => x * {m}).reduce((s, x) => s + x, 0);\nconsole.log(r);'
    return Item('js_array_reduce', 'javascript', level, 'number', 'Что выведет код?', ans, [], code)


# ── web ──────────────────────────────────────────────────────────────────────
@family('web_specificity', 'web')
def web_specificity(rng: random.Random, level: int) -> Item:
    color = rng.sample(['red', 'blue', 'green', 'orange', 'purple', 'teal', 'navy', 'olive', 'maroon'], 3)
    cls = rng.choice(['card', 'item', 'box', 'tile', 'panel', 'note', 'chip', 'badge'])
    idn = rng.choice(['main', 'hero', 'top', 'promo', 'intro', 'footer', 'aside', 'cta'])
    rules = [f'#{idn} {{ color: {color[0]}; }}', f'.{cls} {{ color: {color[1]}; }}', f'div {{ color: {color[2]}; }}']
    rng.shuffle(rules)  # порядок правил не важен: побеждает специфичность
    code = f'<div id="{idn}" class="{cls}">Текст</div>\n\n' + '\n'.join(rules)
    return _single(
        rng, 'web_specificity', 'web', level, 'Каким цветом будет текст?', color[0], [color[1], color[2], 'black'], code
    )


@family('web_flex_width', 'web')
def web_flex_width(rng: random.Random, level: int) -> Item:
    g1, g2 = rng.randint(1, 3 + level), rng.randint(1, 4 + level)
    width = (g1 + g2) * rng.randint(30, 160)
    basis = rng.choice([0, 50, 100, 120]) if level >= 3 else 0
    width += 2 * basis
    free = width - 2 * basis
    ans = basis + free * g1 // (g1 + g2)
    code = (
        f'.row {{ display: flex; width: {width}px; }}\n'
        f'.a {{ flex: {g1} 1 {basis}px; }}\n.b {{ flex: {g2} 1 {basis}px; }}'
    )
    return Item(
        'web_flex_width',
        'web',
        level,
        'number',
        'Какой будет ширина .a в пикселях (без отступов и рамок)?',
        ans,
        [],
        code,
    )


# ── http ─────────────────────────────────────────────────────────────────────
@family('http_status', 'http', conceptual=True)
def http_status(rng: random.Random, level: int) -> Item:
    cases = [
        ('Ресурс успешно создан запросом POST', 201),
        ('Клиент не авторизован: токен отсутствует', 401),
        ('Пользователь авторизован, но прав на ресурс нет', 403),
        ('Запрос корректен, но конфликтует с текущим состоянием ресурса', 409),
        ('Клиент превысил лимит запросов', 429),
        ('Ответ без тела после успешного DELETE', 204),
        ('Ресурс перемещён навсегда', 301),
        ('Шлюз не дождался ответа от upstream-сервера', 504),
        ('Тело запроса синтаксически верно, но не проходит валидацию', 422),
    ]
    pool = cases[: 3 + level]
    text, code = rng.choice(pool)
    others = rng.sample([c for _, c in cases if c != code], 3)
    return _single(rng, 'http_status', 'http', level, f'Какой HTTP-статус уместен? {text}.', code, others)


@family('http_idempotent', 'http', conceptual=True)
def http_idempotent(rng: random.Random, level: int) -> Item:
    methods = {'GET': True, 'PUT': True, 'DELETE': True, 'POST': False, 'PATCH': False, 'HEAD': True, 'OPTIONS': True}
    chosen = rng.sample(list(methods), 5)
    answer = sorted(i for i, m in enumerate(chosen) if methods[m])
    return Item(
        'http_idempotent', 'http', level, 'multi', 'Какие HTTP-методы по спецификации идемпотентны?', answer, chosen
    )


@family('http_backoff', 'http')
def http_backoff(rng: random.Random, level: int) -> Item:
    base = rng.randint(5, 60) * 10
    factor = 2 if level < 3 else rng.choice([2, 3])
    retries = rng.randint(2, 2 + level)
    timeout = rng.randint(2, 40) * 50  # каждый запрос висит до таймаута
    # На старших уровнях пауза ограничена сверху — надо заметить, где срабатывает потолок.
    cap = base * factor ** max(1, retries - 2) if level >= 4 else None
    waits = [base * factor**i for i in range(retries)]
    if cap is not None:
        waits = [min(w, cap) for w in waits]
    ans = sum(waits) + (retries + 1) * timeout
    stem = (
        f'Каждый запрос к API завершается таймаутом через {timeout} мс. Клиент делает первую попытку и '
        f'до {retries} повторов с экспоненциальной паузой: первая пауза {base} мс, каждая следующая '
        f'в {factor} раза больше'
        + (f', но не больше {cap} мс' if cap is not None else '')
        + '. Через сколько миллисекунд от начала клиент сдастся, если все попытки неудачны?'
    )
    return Item('http_backoff', 'http', level, 'number', stem, ans, [])


# ── sql ──────────────────────────────────────────────────────────────────────
@family('sql_group_having', 'sql')
def sql_group_having(rng: random.Random, level: int) -> Item:
    depts = rng.sample(['dev', 'qa', 'ops', 'hr', 'ml'], 3)
    rows = [(rng.choice(depts), rng.randint(5, 30) * 10) for _ in range(4 + level * 2)]
    thr = rng.choice([1, 2]) if level < 3 else rng.choice([2, 3])
    counts: dict[str, int] = {}
    for d, _ in rows:
        counts[d] = counts.get(d, 0) + 1
    ans = sum(1 for c in counts.values() if c > thr)
    values = ',\n  '.join(f"('{d}', {s})" for d, s in rows)
    code = (
        f'-- employees(dept, salary)\nINSERT INTO employees VALUES\n  {values};\n\n'
        f'SELECT dept FROM employees\nGROUP BY dept\nHAVING COUNT(*) > {thr};'
    )
    return Item('sql_group_having', 'sql', level, 'number', 'Сколько строк вернёт запрос?', ans, [], code)


@family('sql_join_count', 'sql')
def sql_join_count(rng: random.Random, level: int) -> Item:
    users = list(range(1, 3 + level))
    orders = [rng.choice([*users, 99]) for _ in range(2 + level)]
    join_kind = rng.choice(['INNER', 'LEFT']) if level >= 2 else 'INNER'
    inner = sum(1 for o in orders if o in users)
    ans = inner if join_kind == 'INNER' else sum(max(1, orders.count(u)) for u in users)
    code = (
        f'-- users(id): {users}\n-- orders(user_id): {orders}\n\n'
        f'SELECT u.id, o.user_id\nFROM users u\n{join_kind} JOIN orders o ON o.user_id = u.id;'
    )
    return Item('sql_join_count', 'sql', level, 'number', 'Сколько строк вернёт запрос?', ans, [], code)


@family('sql_index', 'sql', min_level=3, conceptual=True)
def sql_index(rng: random.Random, level: int) -> Item:
    col_a, col_b = rng.sample(['city', 'status', 'created_at', 'user_id', 'email'], 2)
    queries = [
        (f"WHERE {col_a} = 'x'", True),
        (f"WHERE {col_a} = 'x' AND {col_b} = 'y'", True),
        (f"WHERE {col_b} = 'y'", False),
        (f"WHERE lower({col_a}) = 'x'", False),
        (f'ORDER BY {col_a}, {col_b}', True),
    ]
    chosen = rng.sample(queries, 4)
    answer = sorted(i for i, q in enumerate(chosen) if q[1])
    if not answer:
        return sql_index(rng, level)
    return Item(
        'sql_index',
        'sql',
        level,
        'multi',
        f'Есть B-tree индекс ({col_a}, {col_b}). Какие условия могут эффективно его использовать?',
        answer,
        [q[0] for q in chosen],
    )


# ── architecture ─────────────────────────────────────────────────────────────
@family('arch_cache_hit', 'architecture')
def arch_cache_hit(rng: random.Random, level: int) -> Item:
    size = rng.randint(2, 2 + level // 2)
    seq = [rng.choice('ABCDE'[: 3 + level // 2]) for _ in range(6 + level)]
    cache: list[str] = []
    hits = 0
    for k in seq:
        if k in cache:
            hits += 1
            cache.remove(k)
        elif len(cache) >= size:
            cache.pop(0)
        cache.append(k)
    stem = f'LRU-кэш вмещает {size} ключа. Сколько будет попаданий (hit) для последовательности обращений?'
    return Item('arch_cache_hit', 'architecture', level, 'number', stem, hits, [], ' → '.join(seq))


@family('arch_patterns', 'architecture', min_level=3, conceptual=True)
def arch_patterns(rng: random.Random, level: int) -> Item:
    cases = [
        (
            'Нужно гарантировать, что событие отправится в брокер тогда и только тогда, когда закоммичена транзакция в БД',
            'Transactional Outbox',
        ),
        ('Нужно согласовать распределённую бизнес-операцию из нескольких сервисов без 2PC, с компенсациями', 'Saga'),
        ('Нужно перестать слать запросы к падающему сервису и быстро возвращать ошибку', 'Circuit Breaker'),
        ('Нужно разделить модели чтения и записи для высоконагруженного чтения', 'CQRS'),
        ('Повтор запроса клиентом не должен создавать дубль платежа', 'Idempotency Key'),
        ('Нужно постепенно заменить монолит новыми сервисами без большого переписывания', 'Strangler Fig'),
    ]
    text, ans = rng.choice(cases[: 2 + level])
    others = rng.sample([c for _, c in cases if c != ans], 3)
    return _single(rng, 'arch_patterns', 'architecture', level, f'Какой паттерн подходит? {text}.', ans, others)


# ── ml / statistics ──────────────────────────────────────────────────────────
@family('ml_metrics', 'ml')
def ml_metrics(rng: random.Random, level: int) -> Item:
    tp, fp, fn = rng.randint(10, 60), rng.randint(5, 40), rng.randint(5, 40)
    metric = rng.choice(['precision', 'recall'] if level < 3 else ['precision', 'recall', 'f1'])
    p, r = tp / (tp + fp), tp / (tp + fn)
    val = {'precision': p, 'recall': r, 'f1': 2 * p * r / (p + r)}[metric]
    ans = round(val * 100)
    stem = f'TP = {tp}, FP = {fp}, FN = {fn}. Чему равен {metric} в процентах (округлите до целого)?'
    return Item('ml_metrics', 'ml', level, 'number', stem, ans, [])


@family('ml_overfit', 'ml', conceptual=True)
def ml_overfit(rng: random.Random, level: int) -> Item:
    tr, va = rng.randint(95, 99), rng.randint(60, 75)
    stem = (
        f'Точность на обучении {tr}%, на валидации {va}%. Какие действия уменьшат переобучение? '
        'Отметьте все подходящие.'
    )
    actions = [
        ('Добавить регуляризацию (L2, dropout)', True),
        ('Увеличить глубину деревьев / число слоёв', False),
        ('Собрать больше обучающих данных', True),
        ('Использовать раннюю остановку', True),
        ('Убрать валидационную выборку и учиться на всём', False),
    ]
    chosen = rng.sample(actions, 4)
    answer = sorted(i for i, a in enumerate(chosen) if a[1])
    if not answer:
        return ml_overfit(rng, level)
    return Item('ml_overfit', 'ml', level, 'multi', stem, answer, [a[0] for a in chosen])


@family('stat_mean_median', 'statistics')
def stat_mean_median(rng: random.Random, level: int) -> Item:
    data = sorted(rng.randint(1, 20) for _ in range(5 + level))
    if rng.random() < 0.5 or level < 2:
        ans = round(sum(data) / len(data), 1)
        what = 'среднее арифметическое (округлите до десятых)'
    else:
        mid = len(data) // 2
        ans = data[mid] if len(data) % 2 else (data[mid - 1] + data[mid]) / 2
        what = 'медиану'
    return Item('stat_mean_median', 'statistics', level, 'number', f'Дана выборка {data}. Найдите {what}.', ans, [])


@family('stat_probability', 'statistics')
def stat_probability(rng: random.Random, level: int) -> Item:
    red, blue = rng.randint(2, 6 + level * 3), rng.randint(2, 6 + level * 3)
    total = red + blue
    if level >= 4:
        green = rng.randint(2, 12)
        total += green
        same = sum(k * (k - 1) for k in (red, blue, green))
        ans = round(same / (total * (total - 1)) * 100)
        stem = (
            f'В урне {red} красных, {blue} синих и {green} зелёных шаров. Достают два шара без возвращения. '
            'Вероятность, что они одного цвета, в процентах (до целого)?'
        )
    elif level <= 2:
        ans = round(red / total * 100)
        stem = f'В урне {red} красных и {blue} синих шаров. Вероятность достать красный, в процентах?'
    else:
        ans = round(red / total * (red - 1) / (total - 1) * 100)
        stem = (
            f'В урне {red} красных и {blue} синих шаров. Достают два шара без возвращения. '
            'Вероятность, что оба красные, в процентах (до целого)?'
        )
    return Item('stat_probability', 'statistics', level, 'number', stem, ans, [])


# ── linux / networks / containers ────────────────────────────────────────────
@family('linux_chmod', 'linux')
def linux_chmod(rng: random.Random, level: int) -> Item:
    def perm(d: int) -> str:
        return ('r' if d & 4 else '-') + ('w' if d & 2 else '-') + ('x' if d & 1 else '-')

    digits = [rng.choice([7, 6, 5, 4]), rng.choice([5, 4, 0, 6]), rng.choice([4, 0, 1, 5])]
    octal = ''.join(map(str, digits))
    ans = ''.join(perm(d) for d in digits)
    distr: list[str] = []
    while len(distr) < 3:
        cand = ''.join(perm(rng.choice([7, 6, 5, 4, 1, 0])) for _ in range(3))
        if cand != ans and cand not in distr:
            distr.append(cand)
    return _single(rng, 'linux_chmod', 'linux', level, f'Какие права даст chmod {octal} file?', ans, distr)


@family('linux_pipeline', 'linux')
def linux_pipeline(rng: random.Random, level: int) -> Item:
    lines = [rng.choice(['ERROR db', 'INFO ok', 'WARN slow', 'ERROR auth', 'INFO ok']) for _ in range(5 + level)]
    word = rng.choice(['ERROR', 'INFO', 'WARN'])
    uniq = level >= 3
    matched = [ln for ln in lines if word in ln]
    ans = len(set(matched)) if uniq else len(matched)
    cmd = f"grep '{word}' app.log | sort | uniq | wc -l" if uniq else f"grep -c '{word}' app.log"
    code = 'app.log:\n' + '\n'.join(lines) + f'\n\n$ {cmd}'
    return Item('linux_pipeline', 'linux', level, 'number', 'Что выведет команда?', ans, [], code)


@family('net_subnet', 'networks')
def net_subnet(rng: random.Random, level: int) -> Item:
    if level <= 2:
        prefix = rng.randint(22 + level * 2, 30)
        hosts = 2 ** (32 - prefix) - 2
        stem = f'Сколько адресов хостов доступно в подсети /{prefix} (без адреса сети и широковещательного)?'
        return Item('net_subnet', 'networks', level, 'number', stem, hosts, [])
    prefix = rng.randint(25, 30) if level < 5 else rng.randint(26, 30)
    size = 2 ** (32 - prefix)
    net = rng.randrange(0, 256, size)
    host = net + rng.randint(1, size - 2)
    a, b, c = rng.randint(10, 192), rng.randint(0, 255), rng.randint(0, 255)
    stem = f'Узел {a}.{b}.{c}.{host}/{prefix}. Какой последний октет у широковещательного адреса его подсети?'
    return Item('net_subnet', 'networks', level, 'number', stem, net + size - 1, [])


@family('net_ports', 'networks', conceptual=True)
def net_ports(rng: random.Random, level: int) -> Item:
    ports = {
        'SSH': 22,
        'HTTPS': 443,
        'DNS': 53,
        'PostgreSQL': 5432,
        'Redis': 6379,
        'SMTP': 25,
        'LDAP': 389,
        'Kafka': 9092,
    }
    names = list(ports)[: 3 + level]
    svc = rng.choice(names)
    others = rng.sample([p for n, p in ports.items() if n != svc], 3)
    return _single(rng, 'net_ports', 'networks', level, f'Какой порт по умолчанию у {svc}?', ports[svc], others)


@family('docker_ports', 'containers')
def docker_ports(rng: random.Random, level: int) -> Item:
    pairs = []
    used: set[int] = set()
    for _ in range(min(1 + level // 2, 3)):
        host = rng.choice([p for p in (8080, 8081, 8000, 5000, 3000, 9000, 15432, 16379) if p not in used])
        used.add(host)
        pairs.append((host, rng.choice([80, 8000, 5432, 6379, 3000])))
    host, cont = rng.choice(pairs)
    flags = ' '.join(f'-p {h}:{c}' for h, c in pairs)
    code = f'docker run -d {flags} myapp'
    stem = f'Приложение внутри контейнера слушает порт {cont}. На какой порт хоста нужно обращаться?'
    if len({c for _, c in pairs}) < len(pairs):
        pairs = pairs[:1]
        host, cont = pairs[0]
        code = f'docker run -d -p {host}:{cont} myapp'
        stem = f'Приложение внутри контейнера слушает порт {cont}. На какой порт хоста нужно обращаться?'
    return Item('docker_ports', 'containers', level, 'number', stem, host, [], code)


@family('docker_layers', 'containers', min_level=2, conceptual=True)
def docker_layers(rng: random.Random, level: int) -> Item:
    code = (
        'FROM python:3.12-slim\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\n'
        'CMD ["python", "main.py"]'
    )
    opts = [
        ('Скопировать сначала requirements.txt, установить зависимости, затем COPY . .', True),
        ('Объединить все инструкции в одну строку RUN', False),
        ('Заменить slim-образ на полный python:3.12', False),
        ('Добавить .dockerignore для исключения лишних файлов из контекста', True),
        ('Перенести CMD в начало Dockerfile', False),
    ]
    chosen = rng.sample(opts, 4)
    answer = sorted(i for i, o in enumerate(chosen) if o[1])
    if not answer:
        return docker_layers(rng, level)
    return Item(
        'docker_layers',
        'containers',
        level,
        'multi',
        'Сборка пересобирает зависимости при любом изменении кода. Что ускорит повторные сборки?',
        answer,
        [o[0] for o in chosen],
        code,
    )


@family('k8s_replicas', 'containers', min_level=3)
def k8s_replicas(rng: random.Random, level: int) -> Item:
    replicas = rng.randint(2, 12 + level * 6)
    max_unavail = rng.randint(0, 3)
    if level >= 4 and rng.random() < 0.6:
        pct = rng.choice([10, 20, 25, 30, 50])
        surge, max_surge = f'{pct}%', -(-replicas * pct // 100)  # проценты maxSurge округляются вверх
    else:
        max_surge = rng.randint(1, 3)
        surge = str(max_surge)
    ans = replicas + max_surge
    code = (
        f'replicas: {replicas}\nstrategy:\n  type: RollingUpdate\n  rollingUpdate:\n'
        f'    maxSurge: {surge}\n    maxUnavailable: {max_unavail}'
    )
    return Item(
        'k8s_replicas',
        'containers',
        level,
        'number',
        'Какое максимальное число подов может существовать одновременно во время раскатки?',
        ans,
        [],
        code,
    )


# ── testing ──────────────────────────────────────────────────────────────────
@family('qa_boundary', 'testing', conceptual=True)
def qa_boundary(rng: random.Random, level: int) -> Item:
    lo, hi = rng.randint(1, 30), rng.randint(40, 120)
    ans = 4 if level < 4 else 6
    stem = f'Поле принимает целые числа от {lo} до {hi} включительно. Сколько значений нужно проверить ' + (
        'по анализу граничных значений (граница и соседнее значение снаружи)?'
        if level < 4
        else 'по трёхточечному анализу границ (снаружи, на границе, внутри)?'
    )
    return Item('qa_boundary', 'testing', level, 'number', stem, ans, [])


@family('qa_pairwise', 'testing')
def qa_pairwise(rng: random.Random, level: int) -> Item:
    params = [rng.randint(2, 4 + level) for _ in range(2 + (level + 1) // 2)]
    full = 1
    for p in params:
        full *= p
    ans = full
    desc = ', '.join(f'параметр {i + 1}: {p} значения' for i, p in enumerate(params))
    return Item(
        'qa_pairwise',
        'testing',
        level,
        'number',
        f'Сколько тест-кейсов даст полный перебор комбинаций? ({desc})',
        ans,
        [],
    )


@family('qa_defect_severity', 'testing', conceptual=True)
def qa_defect_severity(rng: random.Random, level: int) -> Item:
    cases = [
        ('Опечатка в тексте футера', 'Trivial'),
        ('Невозможно оплатить заказ ни одним способом', 'Blocker'),
        ('Фильтр по цене иногда игнорируется, есть обходной путь', 'Major'),
        ('Кнопка смещена на 2px в одном браузере', 'Minor'),
        ('Падение приложения при открытии профиля у 30% пользователей', 'Critical'),
    ]
    text, ans = rng.choice(cases)
    others = [c for _, c in cases if c != ans]
    return _single(
        rng, 'qa_defect_severity', 'testing', level, f'Какая серьёзность (severity) у дефекта: {text}?', ans, others
    )


# ── security ─────────────────────────────────────────────────────────────────
@family('sec_entropy', 'security')
def sec_entropy(rng: random.Random, level: int) -> Item:
    alphabets = [
        ('цифры', 10),
        ('строчные латинские буквы', 26),
        ('латинские буквы обоих регистров', 52),
        ('латинские буквы обоих регистров и цифры', 62),
        ('печатные ASCII-символы', 95),
    ]
    name, size = rng.choice(alphabets[: 2 + level // 2 + 1])
    if level >= 3 and rng.random() < 0.6:
        size = rng.randint(16, 94)
        name = 'собственный набор символов'
    length = rng.randint(4 + level, 8 + level * 3)
    digits = rng.randint(0, 2 + level)
    bits = length * math.log2(size) + digits * math.log2(10)
    ans = math.floor(bits)
    tail = f', затем {digits} случайных цифр' if digits else ''
    stem = (
        f'Пароль генерируется случайно: {length} символов, алфавит — {name} ({size} символов){tail}. '
        'Сколько бит энтропии у такого пароля (округлите вниз до целого)?'
    )
    return Item('sec_entropy', 'security', level, 'number', stem, ans, [])


@family('sec_vuln', 'security', conceptual=True)
def sec_vuln(rng: random.Random, level: int) -> Item:
    cases = [
        ('query = f"SELECT * FROM users WHERE name = \'{name}\'"', 'SQL-инъекция'),
        ('element.innerHTML = location.hash.slice(1)', 'XSS'),
        ('requests.get(request.args["url"])', 'SSRF'),
        ('open("/data/" + request.args["file"]).read()', 'Path Traversal'),
        ('pickle.loads(request.data)', 'Небезопасная десериализация'),
        ('if token == request.headers["X-Token"]:', 'Атака по времени (timing)'),
    ]
    code, ans = rng.choice(cases[: 2 + level])
    others = rng.sample([c for _, c in cases if c != ans], 3)
    return _single(rng, 'sec_vuln', 'security', level, 'Какая уязвимость в фрагменте?', ans, others, code)


@family('sec_hash', 'security', conceptual=True)
def sec_hash(rng: random.Random, level: int) -> Item:
    opts = [
        ('bcrypt / argon2 с солью', True),
        ('MD5 без соли', False),
        ('SHA-256 без соли', False),
        ('Base64-кодирование', False),
        ('scrypt с солью', True),
        ('AES с ключом в коде', False),
    ]
    chosen = rng.sample(opts, 4)
    answer = sorted(i for i, o in enumerate(chosen) if o[1])
    if not answer:
        return sec_hash(rng, level)
    return Item(
        'sec_hash',
        'security',
        level,
        'multi',
        'Какие способы подходят для хранения паролей?',
        answer,
        [o[0] for o in chosen],
    )


def topics(level: int | None = None) -> dict[str, list[str]]:
    """topic → список семейств (только допустимых для уровня, если он задан)."""
    out: dict[str, list[str]] = {}
    for name, (topic, _) in FAMILIES.items():
        if level is None or MIN_LEVEL[name] <= level:
            out.setdefault(topic, []).append(name)
    return out


def generate(family_name: str, seed: int, level: int) -> Item:
    """Детерминированно порождает вариант задания по зерну."""
    _, fn = FAMILIES[family_name]
    return fn(random.Random(seed), level)


def check(item: Item, answer: Any) -> bool:
    """Проверка ответа кандидата."""
    if answer is None or answer == '' or answer == []:
        return False
    try:
        if item.kind == 'single':
            return int(answer) == int(item.answer)
        if item.kind == 'multi':
            given = sorted(int(a) for a in (answer if isinstance(answer, list) else [answer]))
            return given == list(item.answer)
        return abs(float(str(answer).replace(',', '.')) - float(item.answer)) < 1e-6
    except (TypeError, ValueError):
        return False
