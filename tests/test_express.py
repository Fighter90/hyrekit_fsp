"""Экспресс-тест для жюри (FSP-32): гость, 5 заданий, категория и подборка."""

from __future__ import annotations

from uuid import UUID

from httpx import AsyncClient

from app.assessment import engine
from app.assessment.models import AssessmentAttempt
from tests.test_flow import _correct, _register

GUEST = {'specialization': 'backend', 'grade': 'junior', 'consent': True}


async def _guest(client: AsyncClient, **override: object) -> dict[str, str]:
    r = await client.post('/api/v1/auth/guest', json={**GUEST, **override})
    assert r.status_code == 201, r.text
    return {'Authorization': f'Bearer {r.json()["access_token"]}'}


async def _pass(client: AsyncClient, h: dict, grade: str, session) -> dict:  # type: ignore[no-untyped-def]
    view = (await client.post('/api/v1/candidate/assessment/start', json={'grade': grade}, headers=h)).json()
    attempt = await session.get(AssessmentAttempt, UUID(view['id']))
    plan = {p['id']: engine.PlannedItem(**p) for p in attempt.plan}
    for it in view['items']:
        await client.post(
            f'/api/v1/candidate/assessment/{view["id"]}/answer',
            json={'item_id': it['id'], 'answer': _correct(it, plan)},
            headers=h,
        )
    r = await client.post(f'/api/v1/candidate/assessment/{view["id"]}/finish', headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_guest_gets_ready_profile(client: AsyncClient) -> None:
    h = await _guest(client)
    profile = (await client.get('/api/v1/candidate/profile', headers=h)).json()
    assert profile['is_guest'] is True
    assert profile['specialization'] == 'backend'
    assert profile['declared_grade'] == 'junior'
    assert profile['consent_given_at']
    me = (await client.get('/api/v1/auth/me', headers=h)).json()
    assert me['is_verified'] is True
    assert me['role'] == 'candidate'


async def test_guest_starts_express_attempt(client: AsyncClient) -> None:
    h = await _guest(client)
    r = await client.post('/api/v1/candidate/assessment/start', json={'grade': 'junior'}, headers=h)
    assert r.status_code == 200, r.text
    view = r.json()
    assert view['mode'] == 'express'
    assert len(view['items']) == 5
    assert all('answer' not in it for it in view['items'])
    from datetime import datetime

    span = datetime.fromisoformat(view['deadline_at']) - datetime.fromisoformat(view['started_at'])
    assert span.total_seconds() == 300


async def test_guest_category_appears_in_employer_matches(client: AsyncClient, session) -> None:  # type: ignore[no-untyped-def]
    h = await _guest(client, grade='middle')
    result = await _pass(client, h, 'middle', session)
    assert result['mode'] == 'express'
    assert result['passed'] is True
    assert result['assigned_grade'] == 'middle'
    profile = (await client.get('/api/v1/candidate/profile', headers=h)).json()
    assert profile['category'] == 'backend:middle'
    assert profile['is_visible'] is True

    emp = await _register(client, 'employer')
    await client.put('/api/v1/employer/company', headers=emp, json={'name': 'ООО Жюри', 'industry': 'fintech'})
    vacancy = (
        await client.post(
            '/api/v1/employer/vacancies',
            headers=emp,
            json={
                'title': 'Python-разработчик',
                'description': 'Сервисы на FastAPI',
                'specialization': 'backend',
                'grade_min': 'middle',
                'grade_max': 'senior',
                'stack': ['Python'],
                'salary_from': 200000,
                'salary_to': 300000,
                'is_published': True,
            },
        )
    ).json()
    matches = (await client.get(f'/api/v1/employer/vacancies/{vacancy["id"]}/matches', headers=emp)).json()
    assert any(i['candidate']['id'] == profile['id'] for i in matches['items'])


async def test_guest_can_retake_without_cooldown(client: AsyncClient, session) -> None:  # type: ignore[no-untyped-def]
    h = await _guest(client)
    await _pass(client, h, 'junior', session)
    elig = (await client.get('/api/v1/candidate/assessment/eligibility', headers=h)).json()
    assert elig['locked_until'] is None
    assert 'senior' in elig['allowed_grades']
    r = await client.post('/api/v1/candidate/assessment/start', json={'grade': 'senior'}, headers=h)
    assert r.status_code == 200
    assert r.json()['mode'] == 'express'


async def test_regular_candidate_gets_full_test(client: AsyncClient) -> None:
    h = await _register(client, 'candidate')
    await client.post(
        '/api/v1/candidate/assessment/survey',
        headers=h,
        json={'industry': 'fintech', 'specialization': 'backend', 'experience_years': 2, 'declared_grade': 'junior'},
    )
    view = (await client.post('/api/v1/candidate/assessment/start', json={'grade': 'junior'}, headers=h)).json()
    assert view['mode'] == 'full'
    assert len(view['items']) == 10


async def test_guest_mode_off_returns_404(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), 'guest_mode', False)
    r = await client.post('/api/v1/auth/guest', json=GUEST)
    assert r.status_code == 404


async def test_guest_requires_consent(client: AsyncClient) -> None:
    r = await client.post('/api/v1/auth/guest', json={**GUEST, 'consent': False})
    assert r.status_code == 422
    r = await client.post('/api/v1/auth/guest', json={**GUEST, 'specialization': 'chef'})
    assert r.status_code == 422
