"""Валидация методики HyreKit на синтетических кандидатах.

Что проверяем (ТЗ, требования к оценке и подбору):

1. Равная сложность вариантов — у всех попыток одного грейда одинаковый план сложности.
2. Защита от утечки — доля совпадающих заданий у двух кандидатов одного грейда.
3. Надёжность (test-retest) — корреляция оценок θ при двух независимых попытках.
4. Точность присвоения грейда — сценарий «выбрал грейд → тест → при провале уровнем ниже».
5. Качество подбора — precision@10 и nDCG@10 против подбора по заявленному грейду и по стеку.

Запуск: `PYTHONPATH=src python scripts/validate.py` — печатает отчёт в markdown
и сохраняет его в docs/validation/results.md.
"""

from __future__ import annotations

import math
import os
import random
import statistics
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('SECRET_KEY', 'validation-only-secret-key-not-for-production-use')
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite://')

from app.assessment import calibration, engine
from app.assessment.simulate import simulate
from app.candidates.service import utcnow
from app.catalog.data import GRADE_CODES, GRADE_ORDER, SPEC_BY_CODE, SPEC_CODES
from app.core.seed import VACANCIES
from app.fsp.provider import get_provider
from app.matching.service import grade_fit, norm, required_stack, score_candidate

SEED = 20261010
OUT = Path(__file__).resolve().parents[1] / 'docs' / 'validation' / 'results.md'


def true_grade(theta: float) -> str:
    passed = [g for g in GRADE_CODES if theta >= engine.cut(g)]
    return passed[-1] if passed else GRADE_CODES[0]


def sample_theta(rng: random.Random) -> float:
    grade = rng.choices(GRADE_CODES, weights=[1, 3, 4, 3, 1])[0]
    return engine.cut(grade) + rng.uniform(0.05, 0.95)


def take_test(spec: str, declared: str, theta: float, rng: random.Random) -> tuple[str | None, float]:
    """Сценарий ТЗ: тест на заявленный грейд, при провале — уровнем ниже."""
    grade = declared
    while True:
        res = simulate(spec, grade, theta, rng)
        if res['passed']:
            return grade, res['ability']
        if GRADE_ORDER[grade] == 0:
            return None, res['ability']
        grade = GRADE_CODES[GRADE_ORDER[grade] - 1]


def check_equal_difficulty(rng: random.Random) -> list[str]:
    rows = []
    for grade in GRADE_CODES:
        profiles = {
            tuple(
                sorted(
                    engine.materialize(p).level
                    for p in engine.build_blueprint(spec, grade, rng_seed=rng.randrange(2**62))
                )
            )
            for spec in SPEC_CODES
            for _ in range(200)
        }
        rows.append(f'| {grade} | {len(profiles)} | {sum(next(iter(profiles))) / 10:.1f} |')
    return rows


def fingerprint(item: object) -> tuple:
    """Как кандидат запоминает задание: формулировка, код и набор вариантов (без порядка)."""
    return (item.family, item.stem, item.code, tuple(sorted(map(str, item.options))))  # type: ignore[attr-defined]


def check_exposure(rng: random.Random, leaked: int = 200, n: int = 300) -> dict[str, object]:
    """Утечка: для каждого направления по Middle слито 200 чужих попыток с ответами.

    Экспозиция семейства — доля заданий новой попытки, которые дословно встречались
    в слитых попытках (кандидат мог выучить ответ). Атака: кандидат уровня Junior
    отвечает сам, а где задание совпало со слитым, — по шпаргалке. Сравниваем со
    статичным тестом, у которого утёк единственный вариант.
    """
    from app.assessment.simulate import answer_attempt, correct_answer

    seen_hits: Counter[str] = Counter()
    seen_total: Counter[str] = Counter()
    exposed_per_attempt: list[int] = []
    honest = cheat = total = 0
    theta = engine.cut('junior') + 0.5
    for spec in SPEC_CODES:
        crib = set()
        for _ in range(leaked):
            for p in engine.build_blueprint(spec, 'middle', rng_seed=rng.randrange(2**62)):
                crib.add(fingerprint(engine.materialize(p)))
        for _ in range(n):
            plan = engine.build_blueprint(spec, 'middle', rng_seed=rng.randrange(2**62))
            own = answer_attempt(plan, theta, rng)
            forged = dict(own)
            exposed = 0
            for p in plan:
                item = engine.materialize(p)
                hit = fingerprint(item) in crib
                seen_total[p.family] += 1
                seen_hits[p.family] += hit
                if hit:
                    exposed += 1
                    forged[p.id] = correct_answer(item)
            exposed_per_attempt.append(exposed)
            honest += engine.decide(engine.score_attempt(plan, own, grade='middle')['ability'], 'middle', None).passed
            cheat += engine.decide(engine.score_attempt(plan, forged, grade='middle')['ability'], 'middle', None).passed
            total += 1
    by_family = {f: seen_hits[f] / seen_total[f] for f in seen_total}

    def cls_mean(conceptual: bool) -> float:
        fams = [f for f in by_family if (f in engine.bank.CONCEPTUAL) == conceptual]
        hits = sum(seen_hits[f] for f in fams)
        return hits / max(1, sum(seen_total[f] for f in fams))

    return {
        'by_family': by_family,
        'generative': cls_mean(False),
        'conceptual': cls_mean(True),
        'exposed_mean': statistics.mean(exposed_per_attempt),
        'honest': honest / total,
        'cheat': cheat / total,
    }


def check_retest(rng: random.Random, n: int = 400) -> tuple[float, float, float]:
    xs, ys, agree = [], [], 0
    for _ in range(n):
        theta = sample_theta(rng)
        spec = rng.choice(SPEC_CODES)
        grade = true_grade(theta)
        r1, r2 = simulate(spec, grade, theta, rng), simulate(spec, grade, theta, rng)
        xs.append(r1['ability'])
        ys.append(r2['ability'])
        agree += r1['passed'] == r2['passed']
    r = statistics.correlation(xs, ys)
    sem = statistics.pstdev([x - y for x, y in zip(xs, ys, strict=True)]) / math.sqrt(2)
    return r, agree / n, sem


def check_discrimination(rng: random.Random, n: int = 1500) -> list[tuple[str, int, float, float]]:
    """Дискриминативность семейств: точечно-бисериальная корреляция «верно/неверно» с θ.

    Классический анализ заданий: одну и ту же форму теста грейда g проходят
    кандидаты с разбросом способностей вокруг этого грейда (θ = cut(g) + 0.5 + N(0, 1)),
    как и бывает в жизни — на грейд заявляются и сильнее, и слабее. Для каждого
    семейства считаем корреляцию ответа с θ; ниже 0.2 — задание на переработку.
    """
    from app.assessment.simulate import answer_attempt

    obs: dict[str, list[tuple[int, float]]] = {}
    solved: dict[str, list[int]] = {}
    for _ in range(n):
        grade = rng.choice(GRADE_CODES)
        theta = engine.cut(grade) + 0.5 + rng.gauss(0, 1)
        spec = rng.choice(SPEC_CODES)
        plan = engine.build_blueprint(spec, grade, rng_seed=rng.randrange(2**62))
        answers = answer_attempt(plan, theta, rng)
        for p in plan:
            ok = int(engine.bank.check(engine.materialize(p), answers[p.id]))
            obs.setdefault(p.family, []).append((ok, theta))
            solved.setdefault(p.family, []).append(ok)
    rows = []
    for fam, pairs in sorted(obs.items()):
        ys = [y for y, _ in pairs]
        if len(set(ys)) < 2:
            continue
        r = statistics.correlation([float(y) for y in ys], [t for _, t in pairs])
        rows.append((fam, len(pairs), statistics.mean(solved[fam]), r))
    return rows


def check_classification(rng: random.Random, n: int = 600) -> dict[str, float]:
    exact = within = overstated = declared_exact = 0
    confusion: Counter[tuple[str, str]] = Counter()
    for _ in range(n):
        theta = sample_theta(rng)
        truth = true_grade(theta)
        # 40 % кандидатов завышают свой уровень на ступень — типичная ситуация с резюме.
        bump = 1 if rng.random() < 0.4 else 0
        declared = GRADE_CODES[min(len(GRADE_CODES) - 1, GRADE_ORDER[truth] + bump)]
        assigned, _ = take_test(rng.choice(SPEC_CODES), declared, theta, rng)
        assigned = assigned or GRADE_CODES[0]
        confusion[(truth, assigned)] += 1
        exact += assigned == truth
        within += abs(GRADE_ORDER[assigned] - GRADE_ORDER[truth]) <= 1
        overstated += GRADE_ORDER[assigned] > GRADE_ORDER[truth]
        declared_exact += declared == truth
    return {
        'exact': exact / n,
        'within_one': within / n,
        'overstated': overstated / n,
        'declared_exact': declared_exact / n,
        'confusion': confusion,  # type: ignore[dict-item]
    }


def make_pool(spec: str, rng: random.Random, n: int = 150) -> list[SimpleNamespace]:
    hints = SPEC_BY_CODE[spec]['stack_hints']
    now = utcnow()
    pool = []
    for _ in range(n):
        theta = sample_theta(rng)
        truth = true_grade(theta)
        bump = 1 if rng.random() < 0.4 else 0
        declared = GRADE_CODES[min(len(GRADE_CODES) - 1, GRADE_ORDER[truth] + bump)]
        grade, ability = take_test(spec, declared, theta, rng)
        if grade is None:
            continue
        fsp_id = f'FSP-{rng.randint(10_000, 99_999)}' if rng.random() < 0.6 else None
        pool.append(
            SimpleNamespace(
                specialization=spec,
                grade=grade,
                ability=ability,
                declared=declared,
                truth=truth,
                theta=theta,
                test_score=None,
                stack=rng.sample(hints, k=rng.randint(2, len(hints))),
                fsp_snapshot=get_provider().fetch(fsp_id) if fsp_id else None,
                last_activity_at=now - timedelta(days=rng.randint(0, 150)),
            )
        )
    return pool


def relevant(c: SimpleNamespace, v: SimpleNamespace, req: list[str]) -> int:
    """Эталон: истинный уровень в диапазоне вакансии и ≥ 60 % требуемого стека."""
    have = {norm(t) for t in c.stack}
    overlap = sum(norm(t) in have for t in req) / len(req)
    return int(grade_fit(c.truth, v.grade_min, v.grade_max) == 100 and overlap >= 0.6)


def precision_ndcg(ranked: list[SimpleNamespace], rel: dict[int, int], k: int = 10) -> tuple[float, float]:
    top = ranked[:k]
    p = sum(rel[id(c)] for c in top) / k
    dcg = sum(rel[id(c)] / math.log2(i + 2) for i, c in enumerate(top))
    ideal = sorted(rel.values(), reverse=True)[:k]
    idcg = sum(r / math.log2(i + 2) for i, r in enumerate(ideal))
    return p, (dcg / idcg if idcg else 0.0)


def check_matching(rng: random.Random, rounds: int = 20) -> list[tuple[str, float, float, float, float, float, float]]:
    rows = []
    for spec_v in VACANCIES:
        v = SimpleNamespace(**spec_v)
        req = required_stack(v)  # type: ignore[arg-type]
        acc = {'ours': [], 'declared': [], 'stack': []}
        for _ in range(rounds):
            pool = make_pool(v.specialization, rng)
            rel = {id(c): relevant(c, v, req) for c in pool}
            ours = sorted(pool, key=lambda c: -score_candidate(c, v, req)['score'])  # type: ignore[arg-type]

            def overlap(c: SimpleNamespace, req: list[str] = req) -> float:
                have = {norm(t) for t in c.stack}
                return sum(norm(t) in have for t in req) / len(req)

            def by_declared(c: SimpleNamespace, v: SimpleNamespace = v) -> float:
                return grade_fit(c.declared, v.grade_min, v.grade_max) + 100 * overlap(c)

            def by_stack(c: SimpleNamespace) -> float:
                return overlap(c) + rng.random() * 0.001

            acc['ours'].append(precision_ndcg(ours, rel))
            acc['declared'].append(precision_ndcg(sorted(pool, key=lambda c: -by_declared(c)), rel))
            acc['stack'].append(precision_ndcg(sorted(pool, key=lambda c: -by_stack(c)), rel))
        mean = {k: (statistics.mean(p for p, _ in vs), statistics.mean(n for _, n in vs)) for k, vs in acc.items()}
        rows.append((v.title, *mean['ours'], *mean['declared'], *mean['stack']))
    return rows


def _calibration_run(
    rng: random.Random, n: int, leaked: str | None = None, share: float = 0.0, excluded: frozenset[str] = frozenset()
) -> tuple[list[calibration.FamilyStat], int]:
    """n попыток; доля share кандидатов знает ответы семейства leaked. Возвращает статистику и показы leaked."""
    from app.assessment.simulate import answer_attempt, correct_answer

    observations: list[calibration.Observation] = []
    shown = 0
    for _ in range(n):
        grade = rng.choice(GRADE_CODES)
        theta = engine.cut(grade) + 0.5 + rng.gauss(0, 1)
        plan = engine.build_blueprint(rng.choice(SPEC_CODES), grade, rng_seed=rng.randrange(2**62), excluded=excluded)
        answers = answer_attempt(plan, theta, rng)
        cheat = leaked is not None and rng.random() < share
        for p in plan:
            if p.family == leaked:
                shown += 1
                if cheat:
                    answers[p.id] = correct_answer(engine.materialize(p))
        observations += calibration.attempt_observations(plan, answers, grade)
    return calibration.family_stats(observations), shown


def check_leak_monitoring(rng: random.Random, n: int = 2000) -> dict[str, object]:
    """Мониторинг утечек: ложные тревоги на честных данных и обнаружение слитого семейства."""
    honest, _ = _calibration_run(rng, n)
    generative = sorted((s for s in honest if not s.conceptual), key=lambda s: -s.shows)
    leaked = generative[len(generative) // 2].family  # семейство со средним числом показов
    runs = []
    for share in (0.25, 0.5, 0.75):
        stats, _ = _calibration_run(rng, n, leaked, share)
        target = next(s for s in stats if s.family == leaked)
        others = sum(1 for s in stats if s.family != leaked and s.status == 'leak')
        runs.append((share, target, others))
    _, shown_after = _calibration_run(rng, 500, leaked, 0.5, excluded=frozenset({leaked}))
    return {'honest': honest, 'leaked': leaked, 'runs': runs, 'shown_after': shown_after}


def main() -> int:
    rng = random.Random(SEED)
    lines = [
        '# Результаты валидации методики',
        '',
        f'Сгенерировано `scripts/validate.py`, зерно {SEED}. Все кандидаты синтетические: '
        'модельный кандидат с истинной способностью θ отвечает верно с вероятностью σ(θ − b).',
        '',
    ]

    lines += [
        '## 1. Равная сложность вариантов',
        '',
        'Для каждого грейда собрано 1 200 случайных вариантов (6 направлений × 200); уровень берётся '
        'у сгенерированного задания, а не у плана. '
        'Число различных профилей сложности должно быть равно 1.',
        '',
        '| Грейд | Различных профилей сложности | Средний уровень задания |',
        '|---|---|---|',
        *check_equal_difficulty(rng),
        '',
    ]

    exp = check_exposure(rng)
    worst = sorted(exp['by_family'].items(), key=lambda kv: -kv[1])  # type: ignore[union-attr]
    lines += [
        '## 2. Защита от утечки',
        '',
        'Сценарий: по каждому из 6 направлений слито 200 чужих попыток теста Middle вместе с ответами. '
        'Задание считается раскрытым, если новый кандидат получил дословно такое же '
        '(та же формулировка, код и набор вариантов).',
        '',
        '| Показатель | Значение |',
        '|---|---|',
        f'| Раскрыто генеративных заданий | {exp["generative"]:.1%} |',
        f'| Раскрыто концептуальных заданий | {exp["conceptual"]:.1%} |',
        f'| Раскрытых заданий в одной попытке из 10, в среднем | {exp["exposed_mean"]:.1f} |',
        f'| Junior сдаёт Middle честно | {exp["honest"]:.1%} |',
        f'| Junior сдаёт Middle со шпаргалкой из 200 попыток | {exp["cheat"]:.1%} |',
        '| Junior сдаёт статичный тест, у которого утёк единственный вариант | 100% |',
        '',
        'Генеративные задания вычисляют ответ из случайных данных, поэтому шпаргалка к ним почти '
        'не переносится. Концептуальные (понятия, статусы, паттерны) раскрываются быстро, поэтому '
        f'в попытке их не больше {engine.MAX_CONCEPTUAL}, а первое задание каждой темы всегда генеративное.',
        '',
        '| Семейство | Класс | Доля раскрытых |',
        '|---|---|---|',
        *[
            f'| {f} | {"концептуальное" if f in engine.bank.CONCEPTUAL else "генеративное"} | {v:.0%} |'
            for f, v in worst
        ],
        '',
    ]

    r, agree, sem = check_retest(rng)
    lines += [
        '## 3. Надёжность (test-retest)',
        '',
        f'* Корреляция θ между двумя независимыми попытками: **r = {r:.2f}** (400 кандидатов).',
        f'* Совпадение решения «сдал / не сдал»: **{agree:.1%}**.',
        f'* Стандартная ошибка измерения θ: **{sem:.2f}** логита (ширина коридора грейда — 1 логит).',
        '',
    ]

    disc = check_discrimination(rng)
    rs = [r for *_, r in disc]
    lines += [
        '## 3а. Дискриминативность заданий',
        '',
        f'1 500 кандидатов со способностями вокруг заявленного грейда проходят тест этого грейда. '
        f'Медиана корреляции «верно/неверно» '
        f'с θ по {len(disc)} семействам — **{statistics.median(rs):.2f}**, минимум — {min(rs):.2f}. '
        'Порог пригодности задания — 0.2.',
        '',
        '| Семейство | Ответов | Доля верных | r с θ |',
        '|---|---|---|---|',
        *[f'| {f} | {k} | {m:.0%} | {r:.2f} |' for f, k, m, r in disc],
        '',
    ]

    cls = check_classification(rng)
    lines += [
        '## 4. Точность присвоения грейда',
        '',
        '600 кандидатов, 40 % из них заявляют грейд на ступень выше истинного.',
        '',
        '| Метрика | Значение |',
        '|---|---|',
        f'| Заявленный грейд совпадает с истинным | {cls["declared_exact"]:.1%} |',
        f'| Присвоенный по тесту совпадает с истинным | **{cls["exact"]:.1%}** |',
        f'| Ошибка не больше одной ступени | {cls["within_one"]:.1%} |',
        f'| Грейд завышен | {cls["overstated"]:.1%} |',
        '',
        'Матрица ошибок (строки — истинный грейд, столбцы — присвоенный):',
        '',
        '| | ' + ' | '.join(GRADE_CODES) + ' |',
        '|---' * (len(GRADE_CODES) + 1) + '|',
    ]
    conf = cls['confusion']
    for t in GRADE_CODES:
        lines.append(f'| {t} | ' + ' | '.join(str(conf[(t, a)]) for a in GRADE_CODES) + ' |')  # type: ignore[index]
    lines.append('')

    lines += [
        '## 5. Качество подбора',
        '',
        'Для каждой демо-вакансии 20 раз генерируется пул из 150 кандидатов направления. '
        'Эталонно релевантен кандидат, у которого истинный уровень входит в диапазон вакансии '
        'и есть не меньше 60 % требуемого стека.',
        '',
        '| Вакансия | HyreKit P@10 | nDCG@10 | По заявленному грейду P@10 | nDCG@10 '
        '| Только по стеку P@10 | nDCG@10 |',
        '|---|---|---|---|---|---|---|',
    ]
    for title, *vals in check_matching(rng):
        lines.append(f'| {title} | ' + ' | '.join(f'{x:.2f}' for x in vals) + ' |')
    lines.append('')

    leak = check_leak_monitoring(random.Random(SEED + 33))
    honest = leak['honest']
    worst = max(honest, key=lambda s: s.drift)  # type: ignore[attr-defined]
    lines += [
        '## 6. Мониторинг утечек заданий',
        '',
        'Методика — `src/app/assessment/calibration.py`. По каждому ответу θ кандидата оценивается заново '
        'только по генеративным заданиям той же попытки без самого задания; ожидаемая доля верных — σ(θ − b). '
        'Дрейф семейства — доля верных минус ожидаемая, за вычетом общего для всех семейств сдвига. '
        f'Утечка — дрейф выше {calibration.DRIFT_THRESHOLD:.0%} и z выше {calibration.Z_THRESHOLD:g} '
        f'при не меньше чем {calibration.MIN_SHOWS} показах; такое семейство исключается из выдачи.',
        '',
        f'**Честные данные.** 2 000 попыток со способностями вокруг заявленного грейда. Ложных тревог: '
        f'{sum(s.status == "leak" for s in honest)} из {len(honest)} семейств. '  # type: ignore[attr-defined]
        f'Наибольший дрейф — {worst.drift:+.1%} (z = {worst.z:+.1f}, `{worst.family}`).',
        '',
        f'**Симулированная утечка.** Ответы семейства `{leak["leaked"]}` знает часть кандидатов; '
        'они отвечают на него верно, на остальные задания — по своей способности.',
        '',
        '| Знают ответы | Показов | Доля верных | Ожидалось | Дрейф | z | Статус | Ложных тревог по другим |',
        '| --: | --: | --: | --: | --: | --: | -- | --: |',
        *[
            f'| {share:.0%} | {s.shows} | {s.solve_rate:.0%} | {s.expected_rate:.0%} | {s.drift:+.1%} '
            f'| {s.z:+.1f} | {calibration.STATUS_TITLES[s.status]} | {others} |'
            for share, s, others in leak['runs']  # type: ignore[attr-defined]
        ],
        '',
        f'После исключения семейство не выдаётся: в 500 новых попытках показов — {leak["shown_after"]}.',
        '',
        f'Порог {calibration.DRIFT_THRESHOLD:.0%} ниже, чем 15 п.п. из постановки FSP-33: утечка к четверти '
        f'кандидатов даёт дрейф {leak["runs"][0][1].drift:+.1%} и с порогом 15 п.п. прошла бы незамеченной. '  # type: ignore[index]
        f'Честный дрейф доходит до {worst.drift:+.1%}, поэтому семейство исключается, только если и z выше '
        f'{calibration.Z_THRESHOLD:g}: у честных семейств z не больше {max(s.z for s in honest):+.1f}.',  # type: ignore[attr-defined]
        '',
    ]

    report = '\n'.join(lines)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(report + '\n', encoding='utf-8')
    print(report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
