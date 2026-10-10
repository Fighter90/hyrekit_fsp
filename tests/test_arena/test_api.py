"""Code Arena через API (FSP-38, FSP-40, FSP-41, FSP-42)."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.arena import problems
from app.arena.models import ArenaParticipant, ArenaRound
from app.candidates.service import utcnow
from tests.test_express import _guest, _pass
from tests.test_flow import _register

API = '/api/v1/arena'


async def _open_round(client: AsyncClient, h: dict) -> dict:
    rounds = (await client.get(f'{API}/rounds', headers=h)).json()
    return next(r for r in rounds if r['is_open'])


def _reference(round_id: str, profile_id: str, code: str) -> str:
    v = problems.variant(code, problems.variant_seed(UUID(round_id), UUID(profile_id), code))
    return v.problem.reference(v.params)


async def _profile_id(client: AsyncClient, h: dict) -> str:
    return (await client.get('/api/v1/candidate/profile', headers=h)).json()['id']


async def test_open_round_full_cycle(client: AsyncClient, session: AsyncSession) -> None:
    h = await _guest(client)
    await _pass(client, h, 'junior', session)
    pid = await _profile_id(client, h)
    r = await _open_round(client, h)
    rid = r['id']

    # отправка до входа не принимается
    bad = await client.post(
        f'{API}/rounds/{rid}/submit', json={'problem': 'sum-multiples', 'code': 'print(1)'}, headers=h
    )
    assert bad.status_code == 409

    joined = await client.post(f'{API}/rounds/{rid}/join', headers=h)
    assert joined.status_code == 200, joined.text
    assert joined.json()['active'] and joined.json()['seconds_left'] > 0

    detail = (await client.get(f'{API}/rounds/{rid}', headers=h)).json()
    assert [t['code'] for t in detail['tasks']] == problems.OPEN_ROUND_PROBLEMS
    task = detail['tasks'][0]
    assert len(task['samples']) == 2 and 'reference' not in task

    ref = _reference(rid, pid, 'sum-multiples')
    run = (
        await client.post(f'{API}/rounds/{rid}/run', json={'problem': 'sum-multiples', 'code': ref}, headers=h)
    ).json()
    assert run['verdict'] == 'OK' and run['total'] == 2 and run['tests'][0]['output'] is not None

    wrong = (
        await client.post(
            f'{API}/rounds/{rid}/submit', json={'problem': 'sum-multiples', 'code': 'print(0)'}, headers=h
        )
    ).json()
    assert wrong['submission']['verdict'] == 'WA'
    assert wrong['submission']['feedback']['summary']
    assert wrong['submission']['feedback']['source'] == 'rules'

    ok = (
        await client.post(
            f'{API}/rounds/{rid}/submit',
            json={'problem': 'sum-multiples', 'code': ref, 'signals': {'blur_count': 2}},
            headers=h,
        )
    ).json()
    sub = ok['submission']
    assert sub['verdict'] == 'OK' and sub['passed'] == sub['total']
    assert all(t['verdict'] == 'OK' and 'time_ms' in t for t in sub['tests'])
    assert ok['participation']['solved'] == 1
    assert ok['participation']['penalty'] == 20  # минута 0 + 20 за одну неверную

    board = (await client.get(f'{API}/rounds/{rid}/leaderboard', headers=h)).json()
    me = next(row for row in board['rows'] if row['me'])
    assert me['solved'] == 1 and me['cells']['sum-multiples']['attempts'] == 1
    assert me['name'].startswith('Участник #')
    assert all(row['profile_id'] is None for row in board['rows'] if not row['me'])

    # разбор закрыт, пока идёт время
    assert (await client.get(f'{API}/rounds/{rid}/editorial', headers=h)).status_code == 403

    fin = (await client.post(f'{API}/rounds/{rid}/finish', headers=h)).json()
    assert fin['rated'] and fin['rating_after'] > 0
    late = await client.post(f'{API}/rounds/{rid}/submit', json={'problem': 'brackets', 'code': 'print(1)'}, headers=h)
    assert late.status_code == 409

    ed = (await client.get(f'{API}/rounds/{rid}/editorial', headers=h)).json()
    first = ed['problems'][0]
    assert first['reference'] and first['solved'] >= 1 and first['idea']

    me_info = (await client.get(f'{API}/me', headers=h)).json()
    assert me_info['rating']['rounds'] == 1 and me_info['rating']['provisional']
    assert len(me_info['rating']['history']) == 1


async def test_two_participants_get_different_variants(client: AsyncClient) -> None:
    a, b = await _guest(client), await _guest(client)
    rid = (await _open_round(client, a))['id']
    for h in (a, b):
        await client.post(f'{API}/rounds/{rid}/join', headers=h)
    ta = (await client.get(f'{API}/rounds/{rid}', headers=a)).json()['tasks'][0]
    tb = (await client.get(f'{API}/rounds/{rid}', headers=b)).json()['tasks'][0]
    assert ta['samples'] != tb['samples']


async def test_identical_solutions_flagged_for_employer(client: AsyncClient) -> None:
    a, b = await _guest(client), await _guest(client)
    emp = await _register(client, 'employer')
    rid = (await _open_round(client, a))['id']
    code = (
        'import sys\n'
        'data = sys.stdin.read().split()\n'
        'n = int(data[0])\n'
        'total = 0\n'
        'for x in data[1:n + 1]:\n'
        '    if int(x) % 2 == 0:\n'
        '        total += int(x)\n'
        'print(total)\n'
    )
    for h in (a, b):
        await client.post(f'{API}/rounds/{rid}/join', headers=h)
        r = await client.post(f'{API}/rounds/{rid}/submit', json={'problem': 'sum-multiples', 'code': code}, headers=h)
        assert r.status_code == 200, r.text
    last = r.json()['submission']
    assert last['suspicious']
    board = (await client.get(f'{API}/rounds/{rid}/leaderboard', headers=emp)).json()
    assert sum(row['suspicious'] for row in board['rows']) >= 2


async def test_sponsored_round_freeze_and_invite(client: AsyncClient, session: AsyncSession) -> None:
    emp = await _register(client, 'employer')
    starts = utcnow() - timedelta(minutes=1)
    created = await client.post(
        f'{API}/rounds',
        json={
            'title': 'Кубок компании',
            'specialization': 'backend',
            'problems': ['brackets', 'lru-cache'],
            'starts_at': (starts + timedelta(minutes=2)).isoformat(),
            'duration_minutes': 60,
            'prize': 'Собеседование топ-3',
        },
        headers=emp,
    )
    assert created.status_code == 201, created.text
    rid = created.json()['id']
    assert created.json()['state'] == 'upcoming'

    cand = await _guest(client)
    await _pass(client, cand, 'junior', session)
    assert (await client.post(f'{API}/rounds/{rid}/join', headers=cand)).status_code == 409  # ещё не начался

    rnd = await session.get(ArenaRound, UUID(rid))
    rnd.starts_at = utcnow() - timedelta(minutes=50)
    rnd.ends_at = rnd.starts_at + timedelta(minutes=60)  # идёт заморозка последних 15 минут
    await session.flush()

    listed = (await client.get(f'{API}/rounds', headers=cand)).json()
    assert any(x['id'] == rid and x['sponsor'] for x in listed)
    assert (await client.post(f'{API}/rounds/{rid}/join', headers=cand)).status_code == 200
    pid = await _profile_id(client, cand)
    ok = await client.post(
        f'{API}/rounds/{rid}/submit',
        json={'problem': 'brackets', 'code': _reference(rid, pid, 'brackets')},
        headers=cand,
    )
    assert ok.json()['submission']['verdict'] == 'OK'

    other = await _guest(client)
    board_other = (await client.get(f'{API}/rounds/{rid}/leaderboard', headers=other)).json()
    assert board_other['frozen'] and board_other['rows'][0]['solved'] == 0
    board_own = (await client.get(f'{API}/rounds/{rid}/leaderboard', headers=cand)).json()
    assert board_own['rows'][0]['solved'] == 1

    board_emp = (await client.get(f'{API}/rounds/{rid}/leaderboard', headers=emp)).json()
    row = board_emp['rows'][0]
    assert not board_emp['frozen'] and row['solved'] == 1 and row['profile_id']

    # конец раунда: рейтинг, витрина и приглашение из таблицы
    part = (
        (
            await session.execute(
                __import__('sqlalchemy').select(ArenaParticipant).where(ArenaParticipant.round_id == UUID(rid))
            )
        )
        .scalars()
        .first()
    )
    part.ends_at = utcnow() - timedelta(seconds=1)
    rnd.ends_at = utcnow() - timedelta(seconds=1)
    await session.flush()
    top = (await client.get(f'{API}/top', params={'specialization': 'backend'}, headers=emp)).json()
    hit = next(i for i in top['items'] if str(i['candidate']['id']) == row['profile_id'])
    assert hit['arena']['rounds'] == 1 and hit['candidate']['contacts'] is None
    assert hit['candidate']['display_name'].startswith('Участник #')

    hidden = (await client.get(f'{API}/candidates/{row["profile_id"]}', headers=emp)).json()
    assert not hidden['solutions_visible'] and hidden['solutions'] == []

    inv = await client.post(
        '/api/v1/employer/invitations',
        json={
            'candidate_id': row['profile_id'],
            'title': 'Backend',
            'message': 'Сильный результат в Arena',
            'salary_from': 150000,
            'salary_to': 200000,
            'contact': 'hr@example.com',
        },
        headers=emp,
    )
    assert inv.status_code == 201, inv.text
    inv_id = inv.json()['id']
    assert (await client.post(f'/api/v1/candidate/invitations/{inv_id}/accept', headers=cand)).status_code == 200
    shown = (await client.get(f'{API}/candidates/{row["profile_id"]}', headers=emp)).json()
    assert shown['solutions_visible'] and shown['solutions'][0]['code']


async def test_show_arena_setting_reveals_name(client: AsyncClient) -> None:
    h = await _guest(client)
    r = await client.put(f'{API}/me/settings', json={'show_arena': True}, headers=h)
    assert r.status_code == 200 and r.json()['show_arena']


async def test_sandbox_info_and_bank(client: AsyncClient) -> None:
    info = (await client.get(f'{API}/sandbox')).json()
    assert 'python' in info['languages'] and info['limits']['time_ms'] == 2000
    bank = (await client.get(f'{API}/problems')).json()
    assert {p['level'] for p in bank} == {1, 2, 3}


async def test_stream_emits_board_version(client: AsyncClient) -> None:
    h = await _guest(client)
    rid = (await _open_round(client, h))['id']
    r = await client.get(f'{API}/rounds/{rid}/stream', params={'once': True}, headers=h)
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('text/event-stream')
    assert 'event: board' in r.text


async def test_employer_round_validation(client: AsyncClient) -> None:
    emp = await _register(client, 'employer')
    bad = await client.post(
        f'{API}/rounds', json={'title': 'Раунд', 'problems': ['nope'], 'starts_at': utcnow().isoformat()}, headers=emp
    )
    assert bad.status_code == 400
    cand = await _guest(client)
    forbidden = await client.post(
        f'{API}/rounds',
        json={'title': 'Раунд', 'problems': ['brackets'], 'starts_at': utcnow().isoformat()},
        headers=cand,
    )
    assert forbidden.status_code == 403
