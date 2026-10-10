"""Клиент OpenID Connect для входа и привязки через ФСП ID (FSP-20).

Authorization Code + PKCE (S256), discovery, проверка id_token, userinfo.
Провайдер задаётся переменными `FSP_OIDC_*`: пустой issuer — встроенный
тестовый провайдер (`app.fsp.mock_idp`), иначе Keycloak ФСП или любой
OIDC-провайдер. Код не зависит от того, какой провайдер подключён.

`FSP_OIDC_BACKCHANNEL_URL` — внутренний адрес провайдера для запросов
сервер-сервер (discovery, token, jwks, userinfo), когда публичный адрес из
контейнера недоступен. Браузер всегда идёт на публичный адрес.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import get_settings
from app.fsp import mock_idp
from app.fsp.provider import FSP_ID_RE

DISCOVERY_TTL = 3600
LEEWAY = 30  # допуск расхождения часов, секунд


class OidcError(Exception):
    """Ответ провайдера не прошёл проверку."""


@dataclass(frozen=True)
class Identity:
    sub: str
    fsp_id: str
    name: str | None
    email: str | None
    email_verified: bool
    claims: dict[str, Any]


_discovery: dict[str, tuple[float, dict[str, Any]]] = {}
_transport: list[httpx.AsyncBaseTransport | None] = [None]  # подмена транспорта в тестах


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    _transport[0] = transport
    _discovery.clear()


def is_mock() -> bool:
    s = get_settings()
    return not s.fsp_oidc_issuer and s.fsp_oidc_mock


def enabled() -> bool:
    return bool(get_settings().fsp_oidc_issuer) or is_mock()


def issuer() -> str:
    return get_settings().fsp_oidc_issuer.rstrip('/') or mock_idp.issuer()


def client_secret() -> str:
    return get_settings().fsp_oidc_client_secret or (mock_idp.client_secret() if is_mock() else '')


def redirect_uri() -> str:
    return get_settings().public_url.rstrip('/') + '/fsp-callback'


def _backchannel_base() -> str | None:
    s = get_settings()
    if s.fsp_oidc_backchannel_url:
        return s.fsp_oidc_backchannel_url.rstrip('/')
    if is_mock():
        return 'http://127.0.0.1:8000'  # тестовый провайдер живёт в том же процессе приложения
    return None


def backchannel(url: str) -> str:
    """Публичный адрес провайдера → внутренний для запросов сервер-сервер."""
    base = _backchannel_base()
    if not base:
        return url
    root = get_settings().public_url.rstrip('/') if is_mock() else issuer()
    if url.startswith(root):
        return base + url[len(root) :]
    return url


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10, transport=_transport[0], trust_env=_transport[0] is None)


async def discovery() -> dict[str, Any]:
    iss = issuer()
    cached = _discovery.get(iss)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    async with _client() as c:
        r = await c.get(backchannel(f'{iss}/.well-known/openid-configuration'))
    if r.status_code != 200:
        raise OidcError(f'discovery: HTTP {r.status_code}')
    data = r.json()
    if data.get('issuer', '').rstrip('/') != iss:
        raise OidcError('discovery: issuer не совпадает с настроенным')
    _discovery[iss] = (time.monotonic() + DISCOVERY_TTL, data)
    return data


def new_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    return verifier, challenge


async def authorize_url(state: str, nonce: str, challenge: str) -> str:
    meta = await discovery()
    s = get_settings()
    query = urlencode(
        {
            'response_type': 'code',
            'client_id': s.fsp_oidc_client_id,
            'redirect_uri': redirect_uri(),
            'scope': s.fsp_oidc_scope,
            'state': state,
            'nonce': nonce,
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        }
    )
    return f'{meta["authorization_endpoint"]}?{query}'


async def _signing_key(meta: dict[str, Any], header: dict[str, Any]) -> Any:
    alg = header.get('alg')
    if alg == 'HS256':
        return client_secret()
    if alg not in ('RS256', 'ES256', 'PS256'):
        raise OidcError(f'id_token: алгоритм {alg} не поддерживается')
    async with _client() as c:
        r = await c.get(backchannel(meta['jwks_uri']))
    if r.status_code != 200:
        raise OidcError(f'jwks: HTTP {r.status_code}')
    keys = r.json().get('keys', [])
    kid = header.get('kid')
    for key in keys:
        if kid is None or key.get('kid') == kid:
            return jwt.PyJWK(key, algorithm=alg).key
    raise OidcError('id_token: ключ подписи не найден в jwks')


async def exchange(code: str, verifier: str, nonce: str) -> Identity:
    """Код авторизации → проверенный id_token и данные userinfo."""
    meta = await discovery()
    s = get_settings()
    async with _client() as c:
        r = await c.post(
            backchannel(meta['token_endpoint']),
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri(),
                'code_verifier': verifier,
                'client_id': s.fsp_oidc_client_id,
                'client_secret': client_secret(),
            },
            headers={'Accept': 'application/json'},
        )
    if r.status_code != 200:
        detail = (
            r.json().get('error_description')
            if r.headers.get('content-type', '').startswith('application/json')
            else ''
        )
        raise OidcError(f'token: HTTP {r.status_code} {detail or ""}'.strip())
    tokens = r.json()
    id_token = tokens.get('id_token')
    if not id_token:
        raise OidcError('token: нет id_token')
    header = jwt.get_unverified_header(id_token)
    key = await _signing_key(meta, header)
    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=[header['alg']],
            audience=s.fsp_oidc_client_id,
            issuer=meta['issuer'],
            leeway=LEEWAY,
            options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']},
        )
    except jwt.PyJWTError as exc:
        raise OidcError(f'id_token: {exc}') from exc
    if claims.get('nonce') != nonce:
        raise OidcError('id_token: nonce не совпадает')
    if meta.get('userinfo_endpoint') and tokens.get('access_token'):
        async with _client() as c:
            u = await c.get(
                backchannel(meta['userinfo_endpoint']), headers={'Authorization': f'Bearer {tokens["access_token"]}'}
            )
        if u.status_code == 200:
            info = u.json()
            if info.get('sub') != claims['sub']:
                raise OidcError('userinfo: sub не совпадает с id_token')
            claims = {**info, **claims}
    return identity(claims)


def identity(claims: dict[str, Any]) -> Identity:
    raw = claims.get(get_settings().fsp_oidc_id_claim) or claims.get('preferred_username') or ''
    fsp_id = str(raw).strip().upper()
    if not FSP_ID_RE.match(fsp_id):
        raise OidcError('Провайдер не передал ФСП ID')
    return Identity(
        sub=str(claims['sub']),
        fsp_id=fsp_id,
        name=claims.get('name'),
        email=claims.get('email'),
        email_verified=bool(claims.get('email_verified')),
        claims=claims,
    )
