"""Ключ лимита: пользователь из токена, иначе адрес клиента."""

from __future__ import annotations

from uuid import uuid4

from starlette.requests import Request

from app.core.limiter import user_or_ip
from app.core.security import create_access_token


def _request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({'type': 'http', 'headers': raw, 'client': ('203.0.113.7', 5000)})


def test_user_or_ip_prefers_token_subject() -> None:
    uid = uuid4()
    token = create_access_token(uid)
    assert user_or_ip(_request({'Authorization': f'Bearer {token}'})) == f'user:{uid}'
    assert user_or_ip(_request({'Authorization': 'Bearer not-a-jwt'})) == '203.0.113.7'
    assert user_or_ip(_request({})) == '203.0.113.7'
