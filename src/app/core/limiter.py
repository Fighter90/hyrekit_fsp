"""Общий rate limiter для всего приложения (SEC-005)."""

from __future__ import annotations

import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

# Единый экземпляр — импортируется в роутерах и main.py.
# storage_uri настраивается в create_app() через limiter._storage.
limiter = Limiter(key_func=get_remote_address)


def user_or_ip(request: Request) -> str:
    """Ключ лимита для действий вошедшего пользователя: его id, иначе адрес.

    Подпись токена здесь не проверяется: зависимости авторизации отрабатывают
    раньше тела обработчика, и запрос с поддельным токеном получает 401.
    """
    auth = request.headers.get('authorization', '')
    if auth.lower().startswith('bearer '):
        try:
            sub = jwt.decode(auth[7:], options={'verify_signature': False}).get('sub')
        except jwt.PyJWTError:
            sub = None
        if sub:
            return f'user:{sub}'
    return get_remote_address(request)
