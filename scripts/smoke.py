"""Дымовая проверка развёрнутого стенда по сквозному сценарию ТЗ.

Ходит в живой API по HTTP, ничего не знает о базе. Нужны демо-данные (SEED_DEMO=true).

    python scripts/smoke.py                                   # http://localhost:8000, Mailpit на :8025
    python scripts/smoke.py --base https://hyrekit.ru --no-mail

Код выхода 0 — все шаги прошли, 1 — хотя бы один упал.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from uuid import uuid4

import httpx

PASSWORD = 'HyreKit2026'  # noqa: S105 — публичный пароль демо-аккаунтов
results: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = '') -> bool:
    results.append((name, ok, detail))
    print(f'{"OK  " if ok else "FAIL"} {name}{" — " + detail if detail else ""}')
    return ok


def login(c: httpx.Client, email: str) -> dict[str, str]:
    r = c.post('/api/v1/auth/login', json={'email': email, 'password': PASSWORD})
    r.raise_for_status()
    return {'Authorization': f'Bearer {r.json()["access_token"]}'}


def verify_by_mail(c: httpx.Client, mailpit: str, email: str) -> bool:
    for _ in range(20):
        msgs = httpx.get(f'{mailpit}/api/v1/search', params={'query': f'to:{email}'}).json()['messages']
        if msgs:
            body = httpx.get(f'{mailpit}/api/v1/message/{msgs[0]["ID"]}').json()['Text']
            token = re.search(r'/verify/([\w.-]+)', body)
            return bool(token) and c.get(f'/api/v1/auth/verify/{token.group(1)}').status_code == 200
        time.sleep(0.5)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://localhost:8000')
    ap.add_argument('--mailpit', default='http://localhost:8025')
    ap.add_argument('--no-mail', action='store_true', help='не проверять письмо подтверждения')
    args = ap.parse_args()
    c = httpx.Client(base_url=args.base, timeout=30)

    step('API живо', c.get('/health').json().get('status') == 'healthy')
    cat = c.get('/api/v1/catalog').json()
    step('Справочник', len(cat['specializations']) >= 6 and len(cat['grades']) == 5)

    # --- Новый кандидат: регистрация, почта, профиль, опрос, тест ---
    email = f'smoke-{uuid4().hex[:8]}@example.ru'
    r = c.post(
        '/api/v1/auth/register',
        json={'email': email, 'password': PASSWORD, 'full_name': 'Дым Проверкин', 'role': 'candidate'},
    )
    step('Регистрация кандидата', r.status_code == 201, str(r.status_code))
    cand = {'Authorization': f'Bearer {r.json()["access_token"]}'}
    if not args.no_mail:
        step('Письмо подтверждения и переход по ссылке', verify_by_mail(c, args.mailpit, email))
        step('Почта подтверждена', c.get('/api/v1/auth/me', headers=cand).json()['is_verified'] is True)

    r = c.put(
        '/api/v1/candidate/profile',
        headers=cand,
        json={'full_name': 'Дым Проверкин', 'phone': '+79990000000', 'stack': ['Python', 'FastAPI']},
    )
    step('Профиль сохранён', r.status_code == 200)
    pdf = c.get('/api/v1/candidate/profile/pdf', headers=cand)
    step('PDF-профиль', pdf.content.startswith(b'%PDF'), f'{len(pdf.content)} байт')
    r = c.post(
        '/api/v1/candidate/profile/resume', headers=cand, files={'file': ('cv.pdf', pdf.content, 'application/pdf')}
    )
    step('Загрузка и разбор PDF-резюме', r.status_code == 200, str(r.status_code))

    r = c.post(
        '/api/v1/candidate/assessment/survey',
        headers=cand,
        json={
            'industry': 'fintech',
            'specialization': 'backend',
            'experience_years': 3,
            'stack': ['Python'],
            'declared_grade': 'middle',
        },
    )
    step('Опрос', r.status_code == 200)
    view = c.post('/api/v1/candidate/assessment/start', headers=cand, json={'grade': 'middle'}).json()
    items = view.get('items', [])
    step('Тест выдан: 10 заданий', len(items) == 10, f'{len(items)}')
    step('Ответы не утекают во фронтенд', all('answer' not in it for it in items))
    for it in items:
        ans = it['options'][0] if it.get('options') else '0'
        c.post(
            f'/api/v1/candidate/assessment/{view["id"]}/answer', headers=cand, json={'item_id': it['id'], 'answer': ans}
        )
    res = c.post(f'/api/v1/candidate/assessment/{view["id"]}/finish', headers=cand).json()
    step(
        'Результат теста с разбором',
        'passed' in res and bool(res.get('by_topic') or res.get('topics')),
        f'балл {res.get("score")}, решение {res.get("suggestion")}',
    )
    r = c.put('/api/v1/candidate/settings', headers=cand, json={'consent': True, 'fsp_id': 'FSP-123457'})
    fsp = r.json().get('fsp') or {}
    step('Согласие и ФСП ID', r.status_code == 200 and fsp.get('has_history') is True, f'балл ФСП {fsp.get("score")}')

    # --- Работодатель: подборка, тест под вакансию, приглашение ---
    emp = login(c, 'employer@hyrekit.ru')
    step('Роли разграничены', c.get('/api/v1/employer/company', headers=cand).status_code == 403)
    vacs = c.get('/api/v1/employer/vacancies', headers=emp).json()
    step('Демо-вакансии работодателя', len(vacs) >= 3, f'{len(vacs)}')
    vac = next(v for v in vacs if v['specialization'] == 'backend')
    matches = c.get(f'/api/v1/employer/vacancies/{vac["id"]}/matches', headers=emp).json()
    top = matches['items']
    step(
        'Подборка с объяснением',
        bool(top) and bool(top[0]['reasons']),
        f'{len(top)} кандидатов, лучший {top[0]["score"]}',
    )
    scores = [i['score'] for i in top]
    step('Подборка по убыванию соответствия', scores == sorted(scores, reverse=True))
    step('Контакты скрыты до согласия', all(i['candidate']['contacts'] is None for i in top))
    prev = c.get(f'/api/v1/employer/vacancies/{vac["id"]}/assessment', headers=emp).json()
    variants = prev.get('variants', [])
    step('Тест под вакансию: два варианта', len(variants) == 2)
    bank = c.get('/api/v1/employer/candidates', headers=emp, params={'specialization': 'backend'}).json()
    step('Банк кандидатов', bool(bank.get('items', bank)))

    # Приглашаем синтетического кандидата, за которого можем войти и ответить
    tal = login(c, 'talent07@demo.hyrekit.ru')
    prof = c.get('/api/v1/candidate/profile', headers=tal).json()
    r = c.post(
        '/api/v1/employer/invitations',
        headers=emp,
        json={
            'candidate_id': prof['id'],
            'title': 'Разработчик в команду платформы',
            'message': 'Приглашаем на интервью',
            'salary_from': 250000,
            'salary_to': 300000,
            'contact': 'hr@technoplatform.ru',
        },
    )
    step('Приглашение отправлено', r.status_code == 201, r.text[:120] if r.status_code != 201 else '')
    invs = [i for i in c.get('/api/v1/candidate/invitations', headers=tal).json() if i['status'] in ('sent', 'viewed')]
    if step('Кандидат видит приглашение с вилкой', bool(invs) and invs[0]['salary_from'] == 250000):
        r = c.post(f'/api/v1/candidate/invitations/{invs[0]["id"]}/accept', headers=tal)
        step('Приглашение принято', r.json().get('status') == 'accepted')
        card = c.get(f'/api/v1/employer/candidates/{prof["id"]}', headers=emp).json()
        step('Контакты раскрыты работодателю', bool(card.get('contacts')), str(card.get('display_name')))

    # --- Отклик и короткое задание ---
    pub = c.get('/api/v1/candidate/vacancies', headers=cand).json()
    r = c.post(f'/api/v1/candidate/vacancies/{pub[0]["id"]}/apply', headers=cand, json={'message': 'Хочу к вам'})
    step('Отклик на вакансию', r.status_code == 200, str(r.status_code))
    apps = c.get('/api/v1/employer/applications', headers=emp).json()
    step('Работодатель видит отклик', any(a['candidate']['contacts_unlocked'] for a in apps))
    chs = c.get('/api/v1/candidate/challenges', headers=cand).json()
    r = c.post(
        f'/api/v1/candidate/challenges/{chs[0]["id"]}/submit',
        headers=cand,
        json={'answer': 'Кэширую ответ в Redis с TTL, инвалидирую по событию обновления, считаю hit rate.'},
    )
    step('Ответ на короткое задание', r.status_code in (200, 201), str(r.status_code))
    subs = c.get(f'/api/v1/employer/challenges/{chs[0]["id"]}/submissions', headers=emp).json()
    step('Работодатель видит ответ с оценкой', any(s.get('score') is not None for s in subs))

    failed = [n for n, ok, _ in results if not ok]
    print(f'\n{len(results) - len(failed)}/{len(results)} шагов прошли')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
