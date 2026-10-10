"""Нагрузочная проверка ключевых операций: подборка, поиск по банку, карточка, кабинет кандидата.

Виртуальные пользователи параллельно крутят сценарий работодателя и кандидата и пишут время ответа
каждой операции. Нужны демо-данные (SEED_DEMO=true). Вход выполняется один раз на роль: эндпоинты
входа ограничены rate limit, и нагрузка на них не входит в сценарий.

    python scripts/load.py                                  # http://localhost:8000, 50 пользователей, 30 с
    python scripts/load.py --base https://hyrekit.ru --users 20 --duration 60 --out docs/validation/load.md

Режим ``--arena``: N демо-кандидатов входят в открытый раунд Code Arena и одновременно
отправляют решение задачи. Код решения — эталон варианта участника (нужен ``PYTHONPATH=src``),
поэтому все отправки должны получить OK. Вход и отправки идут с одного адреса, поэтому стенд
запускается с выключенными лимитами частоты (``ENVIRONMENT=test``).

    ENVIRONMENT=test scripts/dev.sh                          # в другом терминале
    PYTHONPATH=src python scripts/load.py --arena --users 50
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

PASSWORD = 'HyreKit2026'  # noqa: S105 — публичный пароль демо-аккаунтов


async def login(c: httpx.AsyncClient, email: str) -> dict[str, str]:
    r = await c.post('/api/v1/auth/login', json={'email': email, 'password': PASSWORD})
    r.raise_for_status()
    return {'Authorization': f'Bearer {r.json()["access_token"]}'}


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1))))
    return ordered[k]


async def arena(base: str, users: int, problem: str, out: str | None) -> int:
    from app.arena.problems import variant, variant_seed  # нужен только в этом режиме

    limits = httpx.Limits(max_connections=users, max_keepalive_connections=users)
    async with httpx.AsyncClient(base_url=base, timeout=300, limits=limits) as c:
        heads = [await login(c, f'talent{i + 1:02d}@demo.hyrekit.ru') for i in range(users)]
        rounds = (await c.get('/api/v1/arena/rounds', headers=heads[0])).json()
        round_id = next(r['id'] for r in rounds if r['is_open'])
        codes = []
        for h in heads:
            profile_id = (await c.get('/api/v1/candidate/profile', headers=h)).json()['id']
            await c.post(f'/api/v1/arena/rounds/{round_id}/join', headers=h)
            v = variant(problem, variant_seed(round_id, profile_id, problem))
            codes.append(v.problem.reference(v.params))

        async def submit(h: dict[str, str], code: str) -> tuple[float, str, int]:
            t0 = time.perf_counter()
            r = await c.post(
                f'/api/v1/arena/rounds/{round_id}/submit',
                headers=h,
                json={'problem': problem, 'language': 'python', 'code': code, 'signals': {}},
            )
            ms = (time.perf_counter() - t0) * 1000
            body = r.json() if r.status_code < 500 else {}
            sub = body.get('submission', {})
            return ms, sub.get('verdict') or f'HTTP {r.status_code}', int(sub.get('time_ms') or 0)

        started = time.perf_counter()
        results = await asyncio.gather(*(submit(h, code) for h, code in zip(heads, codes, strict=True)))
        elapsed = time.perf_counter() - started
        sandbox = (await c.get('/api/v1/arena/sandbox', headers=heads[0])).json()

    waits = [r[0] for r in results]
    verdicts: dict[str, int] = defaultdict(int)
    for _, verdict, _ in results:
        verdicts[verdict] += 1
    worst_test = max(r[2] for r in results)
    lines = [
        f'## Code Arena: {users} одновременных отправок — {datetime.now(UTC):%Y-%m-%d}',
        '',
        f'Стенд `{base}`, открытый раунд, задача `{problem}`, у каждого участника свой вариант, решение — эталон '
        f'варианта на Python. Песочница: Landlock ABI {sandbox.get("landlock")}, seccomp '
        f'{"включён" if sandbox.get("seccomp") else "выключен"}, параллельных проверок на процесс — '
        f'{sandbox.get("max_parallel", "?")}. '
        f'Команда: `PYTHONPATH=src python scripts/load.py --arena --users {users}`.',
        '',
        f'Все {users} отправок проверены за {elapsed:.1f} с. Вердикты: '
        + ', '.join(f'{k} — {v}' for k, v in sorted(verdicts.items()))
        + f'. Самый долгий тест внутри песочницы — {worst_test} мс.',
        '',
        '| Ожидание ответа на отправку | p50, мс | p95, мс | max, мс |',
        '| -- | --: | --: | --: |',
        f'| Отправка → вердикт и разбор | {statistics.median(waits):.0f} | {percentile(waits, 95):.0f} '
        f'| {max(waits):.0f} |',
    ]
    report = '\n'.join(lines) + '\n'
    print(report)
    if out:
        Path(out).write_text(report, encoding='utf-8')
    return 0 if verdicts.get('OK') == users else 1


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://localhost:8000')
    ap.add_argument('--users', type=int, default=50, help='одновременных пользователей')
    ap.add_argument('--duration', type=int, default=30, help='секунд нагрузки')
    ap.add_argument('--out', help='куда записать отчёт в Markdown')
    ap.add_argument('--arena', action='store_true', help='одновременные отправки в Code Arena')
    ap.add_argument('--problem', default='sum-multiples', help='задача для режима --arena')
    args = ap.parse_args()
    if args.arena:
        return await arena(args.base, args.users, args.problem, args.out)

    limits = httpx.Limits(max_connections=args.users, max_keepalive_connections=args.users)
    async with httpx.AsyncClient(base_url=args.base, timeout=30, limits=limits) as c:
        emp = await login(c, 'employer@hyrekit.ru')
        cand = await login(c, 'talent01@demo.hyrekit.ru')
        vacancies = (await c.get('/api/v1/employer/vacancies', headers=emp)).json()
        bank = (await c.get('/api/v1/employer/candidates', headers=emp, params={'limit': 100})).json()['items']
        profile_ids = [p['id'] for p in bank]

        employer_ops = [
            (
                'Подборка по потребности',
                lambda: c.get(f'/api/v1/employer/vacancies/{random.choice(vacancies)["id"]}/matches', headers=emp),
            ),
            (
                'Поиск по банку с фильтрами',
                lambda: c.get(
                    '/api/v1/employer/candidates',
                    headers=emp,
                    params={
                        'specialization': random.choice(['backend', 'frontend', 'devops', 'qa']),
                        'has_fsp': random.random() < 0.5,
                    },
                ),
            ),
            (
                'Карточка кандидата',
                lambda: c.get(f'/api/v1/employer/candidates/{random.choice(profile_ids)}', headers=emp),
            ),
            ('Категории', lambda: c.get('/api/v1/employer/categories', headers=emp)),
        ]
        candidate_ops = [
            ('Профиль кандидата', lambda: c.get('/api/v1/candidate/profile', headers=cand)),
            ('Вакансии для кандидата', lambda: c.get('/api/v1/candidate/vacancies', headers=cand)),
            ('Справочник', lambda: c.get('/api/v1/catalog')),
        ]

        times: dict[str, list[float]] = defaultdict(list)
        errors: dict[str, int] = defaultdict(int)
        deadline = time.perf_counter() + args.duration

        async def user(i: int) -> None:
            ops = employer_ops if i % 2 == 0 else candidate_ops
            while time.perf_counter() < deadline:
                name, call = random.choice(ops)
                t0 = time.perf_counter()
                try:
                    r = await call()
                    ok = r.status_code < 400
                except httpx.HTTPError:
                    ok = False
                times[name].append((time.perf_counter() - t0) * 1000)
                if not ok:
                    errors[name] += 1

        started = time.perf_counter()
        await asyncio.gather(*(user(i) for i in range(args.users)))
        elapsed = time.perf_counter() - started

    total = sum(len(v) for v in times.values())
    lines = [
        f'# Нагрузочная проверка — {datetime.now(UTC):%Y-%m-%d}',
        '',
        f'Стенд `{args.base}`, {args.users} одновременных пользователей (половина — работодатели, половина — '
        f'кандидаты), {args.duration} с. Всего {total} запросов, {total / elapsed:.0f} запросов в секунду, '
        f'ошибок {sum(errors.values())}. '
        f'Команда: `python scripts/load.py --users {args.users} --duration {args.duration}`.',
        '',
        '| Операция | Запросов | p50, мс | p95, мс | max, мс | Ошибок |',
        '| -- | --: | --: | --: | --: | --: |',
    ]
    for name, _ in [*employer_ops, *candidate_ops]:
        v = times.get(name) or [0.0]
        lines.append(
            f'| {name} | {len(times.get(name, []))} | {statistics.median(v):.0f} | {percentile(v, 95):.0f} '
            f'| {max(v):.0f} | {errors.get(name, 0)} |'
        )
    report = '\n'.join(lines) + '\n'
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding='utf-8')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
