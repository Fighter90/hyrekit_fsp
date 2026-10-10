"""Вход и привязка ФСП ID через OpenID Connect (FSP-20).

Поток Authorization Code + PKCE, клиентом выступает бэкенд:
1. `POST /auth/fsp/start` — state, nonce и code_verifier кладутся в подписанную
   HttpOnly-cookie, в ответе адрес страницы входа провайдера.
2. Провайдер возвращает браузер на `{PUBLIC_URL}/fsp-callback?code&state`.
3. `POST /auth/fsp/callback` — сверка state с cookie, обмен кода, проверка
   id_token; затем вход (выдача токенов HyreKit) или привязка к профилю.

Подтверждённая привязка хранит `sub` провайдера в `candidate_profiles.fsp_sub`:
один участник ФСП — один профиль, ручной ввод ФСП ID такой отметки не даёт.
"""

import secrets
import time
from typing import Any, Literal

import jwt
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.auth.schemas import TokenResponse
from app.candidates.models import CandidateProfile
from app.candidates.service import get_or_create_profile
from app.core.config import get_settings
from app.core.database import get_session
from app.core.dependencies import get_optional_user
from app.core.exceptions import BadRequest, Conflict, Forbidden
from app.core.limiter import limiter
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.fsp import oidc
from app.fsp.provider import get_provider

router = APIRouter(prefix='/auth/fsp', tags=['ФСП ID'])

COOKIE = 'fsp_oidc'
COOKIE_PATH = '/api/v1/auth/fsp'
FLOW_TTL = 600  # на вход у провайдера — 10 минут
FSP_EMAIL_DOMAIN = 'fsp-id.hyrekit.ru'  # адрес-заглушка, если провайдер не подтвердил почту


class StartRequest(BaseModel):
    mode: Literal['login', 'link'] = 'login'


class StartResponse(BaseModel):
    authorize_url: str


class CallbackRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=256)


class CallbackResponse(BaseModel):
    mode: Literal['login', 'link']
    fsp_id: str
    created: bool = False  # вход создал новый аккаунт кандидата
    tokens: TokenResponse | None = None


class ConfigResponse(BaseModel):
    enabled: bool
    test_provider: bool  # встроенный тестовый провайдер вместо Keycloak ФСП


def _flow_key() -> str:
    return get_settings().secret_key + ':fsp-oidc-flow'


@router.get('/config', response_model=ConfigResponse, summary='Доступен ли вход через ФСП ID')
async def config() -> ConfigResponse:
    return ConfigResponse(enabled=oidc.enabled(), test_provider=oidc.is_mock())


@router.post('/start', response_model=StartResponse, summary='Начать вход или привязку через ФСП ID')
@limiter.limit('20/minute')
async def start(
    request: Request,
    response: Response,
    data: StartRequest,
    user: User | None = Depends(get_optional_user),
) -> StartResponse:
    if not oidc.enabled():
        raise BadRequest('Вход через ФСП ID не настроен')
    if data.mode == 'link' and (user is None or user.role != UserRole.CANDIDATE):
        raise Forbidden('Привязать ФСП ID может только вошедший кандидат')
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    verifier, challenge = oidc.new_pkce()
    try:
        url = await oidc.authorize_url(state, nonce, challenge)
    except (oidc.OidcError, OSError) as exc:
        raise BadRequest(f'Провайдер ФСП ID недоступен: {exc}') from exc
    now = int(time.time())
    flow = {
        'state': state,
        'nonce': nonce,
        'verifier': verifier,
        'mode': data.mode,
        'uid': str(user.id) if data.mode == 'link' and user else None,
        'iat': now,
        'exp': now + FLOW_TTL,
    }
    response.set_cookie(
        COOKIE,
        jwt.encode(flow, _flow_key(), algorithm='HS256'),
        max_age=FLOW_TTL,
        path=COOKIE_PATH,
        httponly=True,
        secure=get_settings().public_url.startswith('https://'),
        samesite='lax',
    )
    return StartResponse(authorize_url=url)


def _read_flow(request: Request, state: str) -> dict[str, Any]:
    raw = request.cookies.get(COOKIE)
    if not raw:
        raise BadRequest('Сессия входа через ФСП ID не найдена или истекла, начните заново')
    try:
        flow = jwt.decode(raw, _flow_key(), algorithms=['HS256'])
    except jwt.PyJWTError:
        raise BadRequest('Сессия входа через ФСП ID истекла, начните заново') from None
    if not secrets.compare_digest(flow['state'].encode(), state.encode()):
        raise BadRequest('Параметр state не совпадает: начните вход заново')
    return flow


async def _profile_by_sub(session: AsyncSession, sub: str) -> CandidateProfile | None:
    return (await session.execute(select(CandidateProfile).where(CandidateProfile.fsp_sub == sub))).scalar_one_or_none()


def _attach(profile: CandidateProfile, ident: oidc.Identity) -> None:
    profile.fsp_id = ident.fsp_id
    profile.fsp_sub = ident.sub
    profile.fsp_snapshot = get_provider().fetch(ident.fsp_id) or {
        'fsp_id': ident.fsp_id,
        'athlete_name': ident.name,
        'achievements': [],
    }


async def _login_user(session: AsyncSession, ident: oidc.Identity) -> tuple[User, bool]:
    """Пользователь для входа: по привязке, по подтверждённой почте или новый кандидат."""
    profile = await _profile_by_sub(session, ident.sub)
    if profile is not None:
        user = await session.get(User, profile.user_id)
        if user is None or not user.is_active or user.deleted_at is not None:
            raise Forbidden('Аккаунт, привязанный к этому ФСП ID, отключён')
        return user, False
    if ident.email and ident.email_verified:
        user = (await session.execute(select(User).where(User.email == ident.email.lower()))).scalar_one_or_none()
        if user is not None and user.role == UserRole.CANDIDATE and user.is_active and user.deleted_at is None:
            profile = await get_or_create_profile(session, user)
            _attach(profile, ident)
            return user, False
    email = (
        ident.email.lower()
        if ident.email and ident.email_verified
        else f'{ident.fsp_id.lower()}-{ident.sub[:8]}@{FSP_EMAIL_DOMAIN}'
    )
    if (await session.execute(select(User.id).where(User.email == email))).first():
        email = f'{ident.fsp_id.lower()}-{secrets.token_hex(4)}@{FSP_EMAIL_DOMAIN}'
    user = User(
        email=email,
        hashed_password=hash_password(secrets.token_urlsafe(24)),
        full_name=ident.name,
        role=UserRole.CANDIDATE,
        is_verified=True,  # личность подтвердил провайдер ФСП ID
    )
    session.add(user)
    await session.flush()
    profile = await get_or_create_profile(session, user)
    if ident.email:
        profile.contact_email = ident.email
    _attach(profile, ident)
    return user, True


@router.post('/callback', response_model=CallbackResponse, summary='Завершить вход или привязку через ФСП ID')
@limiter.limit('20/minute')
async def callback(
    request: Request,
    response: Response,
    data: CallbackRequest,
    user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
) -> CallbackResponse:
    flow = _read_flow(request, data.state)
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    try:
        ident = await oidc.exchange(data.code, flow['verifier'], flow['nonce'])
    except oidc.OidcError as exc:
        raise BadRequest(f'ФСП ID не подтвердил вход: {exc}') from exc
    except OSError as exc:
        raise BadRequest('Провайдер ФСП ID недоступен, попробуйте позже') from exc

    if flow['mode'] == 'link':
        if user is None or str(user.id) != flow['uid']:
            raise Forbidden('Привязку начал другой пользователь: войдите в свой аккаунт и повторите')
        profile = await get_or_create_profile(session, user)
        owner = await _profile_by_sub(session, ident.sub)
        if owner is not None and owner.id != profile.id:
            raise Conflict('Этот ФСП ID уже подтверждён в другом аккаунте HyreKit')
        _attach(profile, ident)
        await session.flush()
        return CallbackResponse(mode='link', fsp_id=ident.fsp_id)

    found, created = await _login_user(session, ident)
    await session.flush()
    return CallbackResponse(
        mode='login',
        fsp_id=ident.fsp_id,
        created=created,
        tokens=TokenResponse(access_token=create_access_token(found.id), refresh_token=create_refresh_token(found.id)),
    )
