"""Вход и привязка через ФСП ID (FSP-20): полный поток OIDC через тестовый провайдер.

Клиент `app.fsp.oidc` ходит к провайдеру по HTTP; здесь его транспорт — то же
приложение через ASGI, поэтому проверяется настоящий обмен: discovery,
страница входа, код, PKCE, id_token, userinfo.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import create_access_token
from app.fsp import mock_idp, oidc
from app.main import create_app

FSP_ID = 'FSP-123457'


@pytest.fixture
async def fsp_client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    oidc.set_transport(transport)
    mock_idp._used_codes.clear()
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        yield ac
    oidc.set_transport(None)


def _local(url: str) -> str:
    parts = urlsplit(url)
    return f'{parts.path}?{parts.query}' if parts.query else parts.path


async def _authorize(
    client: AsyncClient, mode: str = 'login', headers: dict | None = None, fsp_id: str = FSP_ID
) -> dict[str, str]:
    """Старт входа и вход на странице провайдера → параметры возврата (code, state)."""
    r = await client.post('/api/v1/auth/fsp/start', json={'mode': mode}, headers=headers or {})
    assert r.status_code == 200, r.text
    url = r.json()['authorize_url']
    page = await client.get(_local(url))
    assert page.status_code == 200
    assert 'Вход через ФСП ID' in page.text
    params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    r = await client.post(
        '/api/v1/fsp-id/authorize', data={**params, 'fsp_id': fsp_id, 'password': mock_idp.TEST_PASSWORD}
    )
    assert r.status_code == 303, r.text
    back = urlsplit(r.headers['location'])
    assert back.path == '/fsp-callback'
    return {k: v[0] for k, v in parse_qs(back.query).items()}


async def test_config_reports_test_provider(fsp_client: AsyncClient) -> None:
    r = await fsp_client.get('/api/v1/auth/fsp/config')
    assert r.json() == {'enabled': True, 'test_provider': True}
    meta = (await fsp_client.get('/api/v1/fsp-id/.well-known/openid-configuration')).json()
    assert meta['issuer'] == oidc.issuer()
    assert meta['code_challenge_methods_supported'] == ['S256']


async def test_login_creates_verified_candidate(fsp_client: AsyncClient) -> None:
    back = await _authorize(fsp_client)
    r = await fsp_client.post('/api/v1/auth/fsp/callback', json=back)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['mode'] == 'login'
    assert body['created'] is True
    assert body['fsp_id'] == FSP_ID
    h = {'Authorization': f'Bearer {body["tokens"]["access_token"]}'}
    me = (await fsp_client.get('/api/v1/auth/me', headers=h)).json()
    assert me['role'] == 'candidate'
    assert me['is_verified'] is True
    fsp = (await fsp_client.get('/api/v1/candidate/fsp', headers=h)).json()
    assert fsp['fsp_id'] == FSP_ID
    assert fsp['verified'] is True
    assert fsp['has_history'] is True

    # Повторный вход тем же участником — тот же аккаунт
    again = await fsp_client.post('/api/v1/auth/fsp/callback', json=await _authorize(fsp_client))
    assert again.json()['created'] is False
    h2 = {'Authorization': f'Bearer {again.json()["tokens"]["access_token"]}'}
    assert (await fsp_client.get('/api/v1/auth/me', headers=h2)).json()['id'] == me['id']


async def test_code_is_single_use_and_state_checked(fsp_client: AsyncClient) -> None:
    back = await _authorize(fsp_client)
    bad = await fsp_client.post('/api/v1/auth/fsp/callback', json={**back, 'state': 'другой'})
    assert bad.status_code == 400
    assert 'state' in bad.json()['message']
    ok = await fsp_client.post('/api/v1/auth/fsp/callback', json=back)
    assert ok.status_code == 200
    # cookie потока удалена после первого обмена
    reuse = await fsp_client.post('/api/v1/auth/fsp/callback', json=back)
    assert reuse.status_code == 400


async def test_provider_rejects_reused_code_and_wrong_verifier(fsp_client: AsyncClient) -> None:
    verifier, challenge = oidc.new_pkce()
    url = await oidc.authorize_url('st', 'nn', challenge)
    params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    r = await fsp_client.post(
        '/api/v1/fsp-id/authorize', data={**params, 'fsp_id': FSP_ID, 'password': mock_idp.TEST_PASSWORD}
    )
    code = parse_qs(urlsplit(r.headers['location']).query)['code'][0]
    form = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': oidc.redirect_uri(),
        'client_id': 'hyrekit',
        'client_secret': oidc.client_secret(),
    }
    wrong = await fsp_client.post('/api/v1/fsp-id/token', data={**form, 'code_verifier': 'не-тот'})
    assert wrong.status_code == 400
    assert wrong.json()['error'] == 'invalid_grant'
    bad_secret = await fsp_client.post(
        '/api/v1/fsp-id/token', data={**form, 'code_verifier': verifier, 'client_secret': 'x'}
    )
    assert bad_secret.status_code == 401
    good = await fsp_client.post('/api/v1/fsp-id/token', data={**form, 'code_verifier': verifier})
    assert good.status_code == 200
    assert good.json()['id_token']
    again = await fsp_client.post('/api/v1/fsp-id/token', data={**form, 'code_verifier': verifier})
    assert again.status_code == 400


async def test_nonce_mismatch_is_rejected(fsp_client: AsyncClient) -> None:
    verifier, challenge = oidc.new_pkce()
    url = await oidc.authorize_url('st', 'nonce-1', challenge)
    params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    r = await fsp_client.post(
        '/api/v1/fsp-id/authorize', data={**params, 'fsp_id': FSP_ID, 'password': mock_idp.TEST_PASSWORD}
    )
    code = parse_qs(urlsplit(r.headers['location']).query)['code'][0]
    with pytest.raises(oidc.OidcError, match='nonce'):
        await oidc.exchange(code, verifier, 'nonce-2')


async def test_deny_and_wrong_password(fsp_client: AsyncClient) -> None:
    r = await fsp_client.post('/api/v1/auth/fsp/start', json={'mode': 'login'})
    params = {k: v[0] for k, v in parse_qs(urlsplit(r.json()['authorize_url']).query).items()}
    wrong = await fsp_client.post('/api/v1/fsp-id/authorize', data={**params, 'fsp_id': FSP_ID, 'password': 'нет'})
    assert wrong.status_code == 200
    assert 'Неверный ФСП ID или пароль' in wrong.text
    deny = await fsp_client.post('/api/v1/fsp-id/authorize', data={**params, 'action': 'deny'})
    assert deny.status_code == 303
    assert parse_qs(urlsplit(deny.headers['location']).query)['error'] == ['access_denied']


async def test_authorize_rejects_foreign_redirect(fsp_client: AsyncClient) -> None:
    challenge = base64.urlsafe_b64encode(hashlib.sha256(b'v').digest()).rstrip(b'=').decode()
    r = await fsp_client.get(
        '/api/v1/fsp-id/authorize',
        params={
            'client_id': 'hyrekit',
            'redirect_uri': 'https://evil.example/cb',
            'response_type': 'code',
            'scope': 'openid',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        },
    )
    assert r.status_code == 400


async def test_link_marks_fsp_verified_and_is_unique(fsp_client: AsyncClient, test_user, employer_user) -> None:  # type: ignore[no-untyped-def]
    h = {'Authorization': f'Bearer {create_access_token(test_user.id)}'}
    # Ручной ввод — без подтверждения
    await fsp_client.put('/api/v1/candidate/settings', json={'fsp_id': 'FSP-555551'}, headers=h)
    assert (await fsp_client.get('/api/v1/candidate/fsp', headers=h)).json()['verified'] is False

    back = await _authorize(fsp_client, mode='link', headers=h)
    r = await fsp_client.post('/api/v1/auth/fsp/callback', json=back, headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {'mode': 'link', 'fsp_id': FSP_ID, 'created': False, 'tokens': None}
    fsp = (await fsp_client.get('/api/v1/candidate/fsp', headers=h)).json()
    assert fsp['fsp_id'] == FSP_ID
    assert fsp['verified'] is True

    # Тот же участник ФСП не привязывается ко второму аккаунту
    other = await fsp_client.post(
        '/api/v1/auth/register',
        json={'email': 'second@example.com', 'password': 'Second1234', 'full_name': 'Второй', 'role': 'candidate'},
    )
    h2 = {'Authorization': f'Bearer {other.json()["access_token"]}'}
    back2 = await _authorize(fsp_client, mode='link', headers=h2)
    dup = await fsp_client.post('/api/v1/auth/fsp/callback', json=back2, headers=h2)
    assert dup.status_code == 409

    # Вход через ФСП ID ведёт в привязанный аккаунт
    login = await fsp_client.post('/api/v1/auth/fsp/callback', json=await _authorize(fsp_client))
    assert login.json()['created'] is False
    hl = {'Authorization': f'Bearer {login.json()["tokens"]["access_token"]}'}
    assert (await fsp_client.get('/api/v1/auth/me', headers=hl)).json()['id'] == str(test_user.id)

    # Ручная смена ID снимает подтверждение
    await fsp_client.put('/api/v1/candidate/settings', json={'fsp_id': 'FSP-555551'}, headers=h)
    assert (await fsp_client.get('/api/v1/candidate/fsp', headers=h)).json()['verified'] is False

    # Работодатель и аноним не привязывают ФСП ID
    he = {'Authorization': f'Bearer {create_access_token(employer_user.id)}'}
    assert (await fsp_client.post('/api/v1/auth/fsp/start', json={'mode': 'link'}, headers=he)).status_code == 403
    assert (await fsp_client.post('/api/v1/auth/fsp/start', json={'mode': 'link'})).status_code == 403


async def test_link_callback_requires_same_user(fsp_client: AsyncClient, test_user) -> None:  # type: ignore[no-untyped-def]
    h = {'Authorization': f'Bearer {create_access_token(test_user.id)}'}
    back = await _authorize(fsp_client, mode='link', headers=h)
    r = await fsp_client.post('/api/v1/auth/fsp/callback', json=back)
    assert r.status_code == 403
