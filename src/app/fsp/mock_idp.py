"""Тестовый провайдер ФСП ID — OpenID Connect для стенда без Keycloak (FSP-20).

Реестр и Keycloak ФСП в хакатоне недоступны, поэтому приложение поднимает
собственный OIDC-провайдер с тем же протоколом: discovery, страница входа,
Authorization Code + PKCE (S256), token, userinfo. Клиентская часть
(`app.fsp.oidc`) работает с ним по HTTP так же, как работала бы с Keycloak;
переход на настоящий провайдер — переменные `FSP_OIDC_*`, без изменений кода.

Учётные записи — участники эмулятора реестра (`MockFspProvider`): любой
ФСП ID формата FSP-NNNN… с тестовым паролем `TEST_PASSWORD`.

Провайдер не хранит состояние, чтобы работать на нескольких воркерах:
код авторизации и access-токен — подписанные JWT с коротким сроком.
id_token подписан HS256 секретом клиента (OIDC Core 10.1, конфиденциальный
клиент); у Keycloak будет RS256 с ключами из jwks_uri — клиент поддерживает оба.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import time
import uuid
from typing import Annotated, Any
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.config import get_settings
from app.fsp.provider import FSP_ID_RE, MockFspProvider

PATH = '/api/v1/fsp-id'
TEST_PASSWORD = 'fsp2026'  # noqa: S105 — публичный пароль тестового стенда, показан на странице входа
CODE_TTL = 120
ACCESS_TTL = 600
ID_TOKEN_TTL = 600
TEST_ACCOUNTS = [('FSP-123457', 'есть история соревнований'), ('FSP-123450', 'истории пока нет')]

router = APIRouter(prefix=PATH, tags=['Тестовый провайдер ФСП ID'])
_used_codes: dict[str, float] = {}  # одноразовость кода в пределах воркера


def issuer() -> str:
    return get_settings().public_url.rstrip('/') + PATH


def _derive(label: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, label.encode(), hashlib.sha256).hexdigest()


def client_secret() -> str:
    """Секрет клиента HyreKit у тестового провайдера."""
    return get_settings().fsp_oidc_client_secret or _derive('fsp-oidc-client')


def _idp_key() -> str:
    return _derive('fsp-oidc-idp')


def subject(fsp_id: str) -> str:
    """Стабильный sub участника, как UUID пользователя в Keycloak."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'{issuer()}#{fsp_id}'))


def _allowed_redirect(uri: str) -> bool:
    return uri == get_settings().public_url.rstrip('/') + '/fsp-callback'


def _claims(fsp_id: str) -> dict[str, Any]:
    raw = MockFspProvider().fetch(fsp_id) or {}
    name = raw.get('athlete_name') or fsp_id
    first, _, last = name.partition(' ')
    return {
        'sub': subject(fsp_id),
        'fsp_id': fsp_id,
        'preferred_username': fsp_id,
        'name': name,
        'given_name': first,
        'family_name': last,
        'email': f'{fsp_id.lower()}@id.fsp.test',
        'email_verified': False,  # адрес тестового стенда не настоящий
    }


@router.get('/.well-known/openid-configuration', summary='OIDC discovery')
async def discovery() -> dict[str, Any]:
    base = issuer()
    return {
        'issuer': base,
        'authorization_endpoint': f'{base}/authorize',
        'token_endpoint': f'{base}/token',
        'userinfo_endpoint': f'{base}/userinfo',
        'jwks_uri': f'{base}/jwks',
        'response_types_supported': ['code'],
        'grant_types_supported': ['authorization_code'],
        'subject_types_supported': ['public'],
        'id_token_signing_alg_values_supported': ['HS256'],
        'code_challenge_methods_supported': ['S256'],
        'token_endpoint_auth_methods_supported': ['client_secret_post', 'client_secret_basic'],
        'scopes_supported': ['openid', 'profile', 'email'],
        'claims_supported': ['sub', 'fsp_id', 'preferred_username', 'name', 'email', 'email_verified'],
    }


@router.get('/jwks', summary='Ключи подписи (у тестового провайдера HS256, публичных ключей нет)')
async def jwks() -> dict[str, Any]:
    return {'keys': []}


def _page(params: dict[str, str], error: str | None = None, fsp_id: str = '') -> HTMLResponse:
    hidden = ''.join(
        f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">' for k, v in params.items()
    )
    accounts = ''.join(
        f'<li><button type="button" class="acc" data-id="{a}">{a}</button> — {html.escape(t)}</li>'
        for a, t in TEST_ACCOUNTS
    )
    err = f'<p class="err" role="alert">{html.escape(error)}</p>' if error else ''
    body = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Вход через ФСП ID</title>
<style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#1b1c21;color:#ededed;
font:15px/1.5 'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace}}
main{{width:min(420px,calc(100% - 32px));background:#2d2e37;border:1px solid rgba(237,237,237,.12);
border-radius:16px;padding:28px}}
h1{{font-size:20px;margin:0 0 4px}} .muted{{color:#a4a5a8;font-size:13px}}
label{{display:block;margin:16px 0 6px;font-size:13px;color:#d9d9d9}}
input{{width:100%;box-sizing:border-box;padding:10px 12px;border-radius:10px;border:1px solid rgba(237,237,237,.18);
background:#121318;color:#ededed;font:inherit}}
.row{{display:flex;gap:10px;margin-top:20px}} button{{font:inherit;cursor:pointer;border-radius:10px;padding:10px 14px;
border:1px solid #8173ff;background:#402fff;color:#fff}} button.ghost{{background:transparent;color:#a4a5a8;
border-color:rgba(237,237,237,.18)}} .acc{{padding:2px 8px;background:transparent;color:#8173ff;border-color:#8173ff}}
ul{{padding-left:18px;margin:8px 0 0}} .err{{color:#ff5468}} .badge{{display:inline-block;font-size:11px;padding:2px 8px;
border-radius:999px;border:1px solid #ffb547;color:#ffb547;margin-bottom:12px}}
</style></head><body><main>
<span class="badge">тестовый стенд</span>
<h1>Вход через ФСП ID</h1>
<p class="muted">HyreKit запрашивает ваше имя, ФСП ID и достижения в соревнованиях ФСП.</p>
{err}
<form method="post" action="{PATH}/authorize">
{hidden}
<label for="fsp_id">ФСП ID</label>
<input id="fsp_id" name="fsp_id" value="{html.escape(fsp_id)}" placeholder="FSP-123457" autocomplete="username" required>
<label for="password">Пароль</label>
<input id="password" name="password" type="password" autocomplete="current-password" required>
<div class="row"><button type="submit" name="action" value="allow">Войти и разрешить</button>
<button type="submit" name="action" value="deny" class="ghost" formnovalidate>Отмена</button></div>
</form>
<p class="muted" style="margin-top:20px">Тестовые участники, пароль <b>{TEST_PASSWORD}</b>:</p><ul class="muted">{accounts}</ul>
<p class="muted">Подойдёт любой ФСП ID формата FSP-NNNNNN.</p>
<script>document.querySelectorAll('.acc').forEach(b=>b.onclick=()=>{{
document.getElementById('fsp_id').value=b.dataset.id;document.getElementById('password').value='{TEST_PASSWORD}'}})</script>
</main></body></html>"""
    return HTMLResponse(body, status_code=400 if error and not params else 200)


def _check_request(client_id: str, redirect_uri: str, response_type: str, method: str, challenge: str) -> None:
    if client_id != get_settings().fsp_oidc_client_id:
        raise HTTPException(400, 'Неизвестный client_id')
    if not _allowed_redirect(redirect_uri):
        raise HTTPException(400, 'redirect_uri не зарегистрирован')
    if response_type != 'code':
        raise HTTPException(400, 'Поддерживается только response_type=code')
    if method != 'S256' or not challenge:
        raise HTTPException(400, 'Нужен PKCE с code_challenge_method=S256')


@router.get('/authorize', response_class=HTMLResponse, summary='Страница входа ФСП ID')
async def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str = 'code',
    scope: str = 'openid',
    state: str = '',
    nonce: str = '',
    code_challenge: str = '',
    code_challenge_method: str = '',
) -> HTMLResponse:
    _check_request(client_id, redirect_uri, response_type, code_challenge_method, code_challenge)
    if 'openid' not in scope.split():
        raise HTTPException(400, 'Нужен scope openid')
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': response_type,
        'scope': scope,
        'state': state,
        'nonce': nonce,
        'code_challenge': code_challenge,
        'code_challenge_method': code_challenge_method,
    }
    return _page(params)


@router.post('/authorize', summary='Вход и согласие на передачу данных')
async def authorize_submit(
    client_id: Annotated[str, Form()],
    redirect_uri: Annotated[str, Form()],
    code_challenge: Annotated[str, Form()],
    response_type: Annotated[str, Form()] = 'code',
    scope: Annotated[str, Form()] = 'openid',
    state: Annotated[str, Form()] = '',
    nonce: Annotated[str, Form()] = '',
    code_challenge_method: Annotated[str, Form()] = 'S256',
    fsp_id: Annotated[str, Form()] = '',
    password: Annotated[str, Form()] = '',
    action: Annotated[str, Form()] = 'allow',
) -> Any:
    _check_request(client_id, redirect_uri, response_type, code_challenge_method, code_challenge)
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': response_type,
        'scope': scope,
        'state': state,
        'nonce': nonce,
        'code_challenge': code_challenge,
        'code_challenge_method': code_challenge_method,
    }
    if action == 'deny':
        query = urlencode({'error': 'access_denied', 'error_description': 'Вход отменён', 'state': state})
        return RedirectResponse(f'{redirect_uri}?{query}', status_code=303)
    fsp_id = fsp_id.strip().upper()
    if not FSP_ID_RE.match(fsp_id) or not hmac.compare_digest(password.encode(), TEST_PASSWORD.encode()):
        return _page(params, 'Неверный ФСП ID или пароль', fsp_id)
    now = int(time.time())
    code = jwt.encode(
        {
            'typ': 'code',
            'jti': uuid.uuid4().hex,
            'fsp_id': fsp_id,
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': scope,
            'nonce': nonce,
            'challenge': code_challenge,
            'iat': now,
            'exp': now + CODE_TTL,
        },
        _idp_key(),
        algorithm='HS256',
    )
    return RedirectResponse(f'{redirect_uri}?{urlencode({"code": code, "state": state})}', status_code=303)


def _token_error(error: str, description: str, status: int = 400) -> JSONResponse:
    return JSONResponse({'error': error, 'error_description': description}, status_code=status)


@router.post('/token', summary='Обмен кода на токены (Authorization Code + PKCE)')
async def token(
    request: Request,
    grant_type: Annotated[str, Form()],
    code: Annotated[str, Form()],
    redirect_uri: Annotated[str, Form()],
    code_verifier: Annotated[str, Form()],
    client_id: Annotated[str | None, Form()] = None,
    secret: Annotated[str | None, Form(alias='client_secret')] = None,
) -> JSONResponse:
    auth = request.headers.get('authorization', '')
    if auth.lower().startswith('basic '):
        try:
            client_id, _, secret = base64.b64decode(auth[6:]).decode().partition(':')
        except (ValueError, UnicodeDecodeError):
            return _token_error('invalid_client', 'Неверная авторизация клиента', 401)
    expected = client_secret()
    if client_id != get_settings().fsp_oidc_client_id or not hmac.compare_digest(
        (secret or '').encode(), expected.encode()
    ):
        return _token_error('invalid_client', 'Неверный client_id или client_secret', 401)
    if grant_type != 'authorization_code':
        return _token_error('unsupported_grant_type', 'Поддерживается authorization_code')
    try:
        data = jwt.decode(code, _idp_key(), algorithms=['HS256'])
    except jwt.PyJWTError:
        return _token_error('invalid_grant', 'Код недействителен или истёк')
    now = time.time()
    for jti, exp in list(_used_codes.items()):
        if exp < now:
            del _used_codes[jti]
    if data.get('typ') != 'code' or data['jti'] in _used_codes:
        return _token_error('invalid_grant', 'Код уже использован')
    if data['client_id'] != client_id or data['redirect_uri'] != redirect_uri:
        return _token_error('invalid_grant', 'Код выдан другому клиенту или redirect_uri')
    digest = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    if not hmac.compare_digest(digest.encode(), data['challenge'].encode()):
        return _token_error('invalid_grant', 'code_verifier не совпадает с code_challenge')
    _used_codes[data['jti']] = data['exp']
    claims = _claims(data['fsp_id'])
    issued = int(now)
    id_token = jwt.encode(
        {
            **claims,
            'iss': issuer(),
            'aud': client_id,
            'iat': issued,
            'auth_time': data['iat'],
            'exp': issued + ID_TOKEN_TTL,
            **({'nonce': data['nonce']} if data['nonce'] else {}),
        },
        expected,
        algorithm='HS256',
    )
    access = jwt.encode(
        {
            'typ': 'access',
            'sub': claims['sub'],
            'fsp_id': data['fsp_id'],
            'scope': data['scope'],
            'exp': issued + ACCESS_TTL,
        },
        _idp_key(),
        algorithm='HS256',
    )
    return JSONResponse(
        {
            'access_token': access,
            'token_type': 'Bearer',
            'expires_in': ACCESS_TTL,
            'id_token': id_token,
            'scope': data['scope'],
        },
        headers={'Cache-Control': 'no-store'},
    )


@router.get('/userinfo', summary='Данные участника по access-токену')
async def userinfo(authorization: Annotated[str, Header()] = '') -> dict[str, Any]:
    if not authorization.lower().startswith('bearer '):
        raise HTTPException(401, 'Нужен Bearer-токен')
    try:
        data = jwt.decode(authorization[7:], _idp_key(), algorithms=['HS256'])
    except jwt.PyJWTError:
        raise HTTPException(401, 'Токен недействителен') from None
    if data.get('typ') != 'access':
        raise HTTPException(401, 'Токен недействителен')
    return _claims(data['fsp_id'])
