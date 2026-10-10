"""FSP-25: журнал согласий с версиями; FSP-45: избранное и подборка до фильтров."""

from __future__ import annotations

from httpx import AsyncClient

from app.candidates.service import CONSENT_VERSION
from tests.test_flow import _pass_test, _register


async def _visible_candidate(client: AsyncClient, session) -> tuple[dict, dict]:  # type: ignore[no-untyped-def]
    cand = await _register(client, 'candidate')
    await client.put(
        '/api/v1/candidate/profile', headers=cand, json={'full_name': 'Ольга Петрова', 'stack': ['Python']}
    )
    await client.post(
        '/api/v1/candidate/assessment/survey',
        headers=cand,
        json={'industry': 'fintech', 'specialization': 'backend', 'experience_years': 3, 'declared_grade': 'middle'},
    )
    assert (await _pass_test(client, cand, 'middle', session))['passed']
    profile = (await client.put('/api/v1/candidate/settings', headers=cand, json={'consent': True})).json()
    return cand, profile


async def _vacancy(client: AsyncClient, emp: dict) -> dict:
    await client.put('/api/v1/employer/company', headers=emp, json={'name': 'ООО Шортлист'})
    r = await client.post(
        '/api/v1/employer/vacancies',
        headers=emp,
        json={
            'title': 'Backend',
            'description': 'Сервисы на Python',
            'specialization': 'backend',
            'grade_min': 'middle',
            'grade_max': 'senior',
            'stack': ['Python'],
            'salary_from': 200000,
            'salary_to': 260000,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_consent_history_keeps_versions(client: AsyncClient, session) -> None:  # type: ignore[no-untyped-def]
    cand, _ = await _visible_candidate(client, session)
    await client.put('/api/v1/candidate/settings', headers=cand, json={'consent': True})  # повтор не пишется
    await client.put('/api/v1/candidate/settings', headers=cand, json={'consent': False})

    log = (await client.get('/api/v1/candidate/consents', headers=cand)).json()
    assert log['current_version'] == CONSENT_VERSION
    assert [e['action'] for e in log['items']] == ['revoked', 'given']
    assert all(e['version'] == CONSENT_VERSION and e['kind'] == 'publication' for e in log['items'])

    profile = (await client.get('/api/v1/candidate/profile', headers=cand)).json()
    assert profile['consent_given_at'] is None
    assert profile['is_visible'] is False


async def test_favorites_follow_consent(client: AsyncClient, session) -> None:  # type: ignore[no-untyped-def]
    cand, profile = await _visible_candidate(client, session)
    emp = await _register(client, 'employer')
    vacancy = await _vacancy(client, emp)

    r = await client.put(
        f'/api/v1/employer/favorites/{profile["id"]}',
        headers=emp,
        json={'vacancy_id': vacancy['id'], 'note': 'сильный'},
    )
    assert r.status_code == 200, r.text
    # повторное добавление не дублирует запись
    await client.put(f'/api/v1/employer/favorites/{profile["id"]}', headers=emp, json={'vacancy_id': vacancy['id']})

    favs = (await client.get('/api/v1/employer/favorites', headers=emp, params={'vacancy_id': vacancy['id']})).json()
    assert [f['candidate']['id'] for f in favs] == [profile['id']]
    assert favs[0]['candidate']['contacts'] is None  # избранное не раскрывает контакты

    card = (await client.get(f'/api/v1/employer/candidates/{profile["id"]}', headers=emp)).json()
    assert card['is_favorite'] is True
    matches = (await client.get(f'/api/v1/employer/vacancies/{vacancy["id"]}/matches', headers=emp)).json()
    assert next(i for i in matches['items'] if i['candidate']['id'] == profile['id'])['candidate']['is_favorite']

    # другая компания избранное этой не видит
    other = await _register(client, 'employer')
    await client.put('/api/v1/employer/company', headers=other, json={'name': 'Другая'})
    assert (await client.get('/api/v1/employer/favorites', headers=other)).json() == []

    # отзыв согласия убирает кандидата из шортлиста
    await client.put('/api/v1/candidate/settings', headers=cand, json={'consent': False})
    assert (await client.get('/api/v1/employer/favorites', headers=emp)).json() == []
    r = await client.put(f'/api/v1/employer/favorites/{profile["id"]}', headers=emp, json={})
    assert r.status_code == 404

    await client.put('/api/v1/candidate/settings', headers=cand, json={'consent': True})
    assert (await client.delete(f'/api/v1/employer/favorites/{profile["id"]}', headers=emp)).status_code == 204
    assert (await client.get('/api/v1/employer/favorites', headers=emp)).json() == []


async def test_matches_keep_base_total_under_filters(client: AsyncClient, session) -> None:  # type: ignore[no-untyped-def]
    await _visible_candidate(client, session)
    emp = await _register(client, 'employer')
    vacancy = await _vacancy(client, emp)
    url = f'/api/v1/employer/vacancies/{vacancy["id"]}/matches'

    base = (await client.get(url, headers=emp)).json()
    narrowed = (await client.get(url, headers=emp, params={'has_fsp': True})).json()
    assert base['base_total'] == base['total'] >= 1
    assert narrowed['base_total'] == base['base_total']
    assert narrowed['total'] < base['total']
