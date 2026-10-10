"""Сквозной сценарий ТЗ: регистрация → опрос → тест → категория → подбор → приглашение."""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient

from app.assessment import bank, engine


async def _register(client: AsyncClient, role: str) -> dict[str, str]:
    email = f'{role}-{uuid4().hex[:8]}@example.com'
    r = await client.post(
        '/api/v1/auth/register',
        json={
            'email': email,
            'password': 'StrongPass1',
            'full_name': f'Тест {role}',
            'role': role,
        },
    )
    assert r.status_code == 201, r.text
    return {'Authorization': f'Bearer {r.json()["access_token"]}'}


def _correct(item: dict, plan: dict[str, engine.PlannedItem]) -> object:
    real = engine.materialize(plan[item['id']])
    return real.answer if real.kind != 'single' else str(real.answer)


async def _pass_test(client: AsyncClient, h: dict, grade: str, session) -> dict:  # type: ignore[no-untyped-def]
    from app.assessment.models import AssessmentAttempt

    r = await client.post('/api/v1/candidate/assessment/start', json={'grade': grade}, headers=h)
    assert r.status_code == 200, r.text
    view = r.json()
    assert all('answer' not in it for it in view['items'])  # правильные ответы не утекают
    attempt = await session.get(AssessmentAttempt, __import__('uuid').UUID(view['id']))
    plan = {p['id']: engine.PlannedItem(**p) for p in attempt.plan}
    for it in view['items']:
        r = await client.post(
            f'/api/v1/candidate/assessment/{view["id"]}/answer',
            json={'item_id': it['id'], 'answer': _correct(it, plan)},
            headers=h,
        )
        assert r.status_code == 200
    r = await client.post(f'/api/v1/candidate/assessment/{view["id"]}/finish', headers=h)
    assert r.status_code == 200
    return r.json()


async def test_full_reverse_hiring_flow(client: AsyncClient, session) -> None:  # type: ignore[no-untyped-def]
    cand = await _register(client, 'candidate')
    emp = await _register(client, 'employer')

    # Роли разграничены
    assert (await client.get('/api/v1/employer/company', headers=cand)).status_code == 403
    assert (await client.get('/api/v1/candidate/profile', headers=emp)).status_code == 403

    r = await client.put(
        '/api/v1/candidate/profile',
        headers=cand,
        json={
            'full_name': 'Мария Иванова',
            'phone': '+79990001122',
            'headline': 'Python backend',
            'stack': ['Python', 'FastAPI', 'PostgreSQL'],
            'salary_from': 200000,
            'salary_to': 260000,
        },
    )
    assert r.status_code == 200
    r = await client.post(
        '/api/v1/candidate/assessment/survey',
        headers=cand,
        json={
            'industry': 'fintech',
            'specialization': 'backend',
            'experience_years': 3,
            'stack': ['Redis'],
            'declared_grade': 'middle',
        },
    )
    assert r.json()['declared_grade'] == 'middle'

    result = await _pass_test(client, cand, 'middle', session)
    assert result['passed'] is True
    assert result['assigned_grade'] == 'middle'
    assert result['suggestion'] == 'try_higher'

    # Смена грейда ограничена по времени
    elig = (await client.get('/api/v1/candidate/assessment/eligibility', headers=cand)).json()
    assert elig['allowed_grades'] == []
    assert elig['locked_until']

    # Без согласия кандидат не виден работодателю
    r = await client.put('/api/v1/candidate/settings', headers=cand, json={'consent': True, 'fsp_id': 'FSP-123457'})
    profile = r.json()
    assert profile['category'] == 'backend:middle'
    assert profile['is_visible']
    assert profile['fsp']['has_history'] is True

    await client.put('/api/v1/employer/company', headers=emp, json={'name': 'ООО Тест', 'industry': 'fintech'})
    r = await client.post(
        '/api/v1/employer/vacancies',
        headers=emp,
        json={
            'title': 'Python-разработчик',
            'description': 'Пишем сервисы платежей на FastAPI и PostgreSQL, Kafka',
            'specialization': 'backend',
            'grade_min': 'middle',
            'grade_max': 'senior',
            'stack': ['Python'],
            'salary_from': 220000,
            'salary_to': 300000,
            'is_published': True,
        },
    )
    assert r.status_code == 201, r.text
    vacancy = r.json()

    matches = (await client.get(f'/api/v1/employer/vacancies/{vacancy["id"]}/matches', headers=emp)).json()
    assert 'Kafka' in matches['required_stack']  # стек извлечён из описания
    item = next(i for i in matches['items'] if i['candidate']['id'] == profile['id'])
    assert item['reasons']
    assert item['missing_stack'] == ['Kafka']
    assert item['candidate']['contacts'] is None  # контакты скрыты до согласия
    assert item['candidate']['display_name'].startswith('Кандидат #')

    r = await client.post(
        '/api/v1/employer/invitations',
        headers=emp,
        json={
            'candidate_id': profile['id'],
            'vacancy_id': vacancy['id'],
            'title': 'Senior? Middle+!',
            'message': 'Приглашаем на интервью в команду платежей',
            'salary_from': 250000,
            'salary_to': 300000,
            'contact': 'hr@test.ru',
        },
    )
    assert r.status_code == 201, r.text
    inv = r.json()

    invs = (await client.get('/api/v1/candidate/invitations', headers=cand)).json()
    assert invs[0]['salary_from'] == 250000
    assert invs[0]['candidate'] is None
    await client.post(f'/api/v1/candidate/invitations/{inv["id"]}/view', headers=cand)
    r = await client.post(f'/api/v1/candidate/invitations/{inv["id"]}/accept', headers=cand)
    assert r.json()['status'] == 'accepted'

    card = (await client.get(f'/api/v1/employer/candidates/{profile["id"]}', headers=emp)).json()
    assert card['contacts']['phone'] == '+79990001122'
    assert card['display_name'] == 'Мария Иванова'

    # Классический отклик
    vacs = (await client.get('/api/v1/candidate/vacancies', headers=cand)).json()
    assert any(v['id'] == vacancy['id'] for v in vacs)
    r = await client.post(f'/api/v1/candidate/vacancies/{vacancy["id"]}/apply', headers=cand, json={})
    assert r.status_code == 200
    apps = (await client.get('/api/v1/employer/applications', headers=emp)).json()
    assert apps[0]['candidate']['contacts_unlocked'] is True
    vacs = (await client.get('/api/v1/candidate/vacancies', headers=cand)).json()
    assert next(v for v in vacs if v['id'] == vacancy['id'])['applications_count'] == 1

    pdf = await client.get('/api/v1/candidate/profile/pdf', headers=cand)
    assert pdf.headers['content-type'] == 'application/pdf'
    assert pdf.content.startswith(b'%PDF')


async def test_failed_test_keeps_grade_and_offers_lower(client: AsyncClient) -> None:
    cand = await _register(client, 'candidate')
    await client.post(
        '/api/v1/candidate/assessment/survey',
        headers=cand,
        json={
            'industry': 'other',
            'specialization': 'frontend',
            'experience_years': 1,
            'declared_grade': 'senior',
        },
    )
    view = (await client.post('/api/v1/candidate/assessment/start', json={'grade': 'senior'}, headers=cand)).json()
    res = (await client.post(f'/api/v1/candidate/assessment/{view["id"]}/finish', headers=cand)).json()
    assert res['passed'] is False
    assert res['suggestion'] == 'retry_lower'
    profile = (await client.get('/api/v1/candidate/profile', headers=cand)).json()
    assert profile['grade'] is None
    elig = (await client.get('/api/v1/candidate/assessment/eligibility', headers=cand)).json()
    assert 'middle' in elig['allowed_grades']  # сразу можно пройти тест ниже


def test_variants_differ_but_difficulty_matches() -> None:
    """Устойчивость к утечкам: два кандидата получают разные варианты одинаковой структуры."""
    a = engine.build_blueprint('backend', 'middle', rng_seed=1)
    b = engine.build_blueprint('backend', 'middle', rng_seed=2)
    assert sorted(p.level for p in a) == sorted(p.level for p in b)
    assert sorted(p.topic for p in a) == sorted(p.topic for p in b)
    stems_a = {engine.materialize(p).stem + str(engine.materialize(p).code) for p in a}
    stems_b = {engine.materialize(p).stem + str(engine.materialize(p).code) for p in b}
    assert stems_a != stems_b
    assert len(bank.FAMILIES) >= 30


async def test_employer_sees_vacancy_test_preview(client, employer_headers) -> None:
    body = {
        'title': 'DevOps',
        'description': 'Kubernetes и Terraform, мониторинг Prometheus',
        'specialization': 'devops',
        'grade_min': 'junior',
        'grade_max': 'middle',
        'stack': ['Docker', 'Linux'],
        'salary_from': 100000,
        'salary_to': 150000,
        'work_format': 'remote',
        'is_published': True,
    }
    v = (await client.post('/api/v1/employer/vacancies', json=body, headers=employer_headers)).json()
    r = await client.get(f'/api/v1/employer/vacancies/{v["id"]}/assessment', headers=employer_headers)
    assert r.status_code == 200
    data = r.json()
    assert data['topics'][0]['topic'] in {'containers', 'linux'}
    assert len(data['variants']) == 2
    assert 'answer' not in data['variants'][0]['items'][0]
