"""Цепочка LLM-провайдеров: GigaChat, затем YandexGPT, затем правила."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.core.exceptions import LLMAuthError, LLMProviderUnavailable
from app.llm import chain, yandexgpt
from app.llm.chain import LLMChain


class _Fake:
    def __init__(self, name: str, reply: str | None = None, *, configured: bool = True, fail: bool = False) -> None:
        self.name, self.title, self._reply, self._configured, self._fail = name, name, reply, configured, fail
        self.calls = 0

    @property
    def is_configured(self) -> bool:
        return self._configured

    async def complete(self, **_: Any) -> str:
        self.calls += 1
        if self._fail:
            raise LLMProviderUnavailable(self.name)
        return self._reply or ''


async def test_first_provider_answers() -> None:
    a, b = _Fake('gigachat', '{"x": 1}'), _Fake('yandexgpt', '{"x": 2}')
    llm = LLMChain([a, b])
    assert await llm.complete_json(system='s', user='u') == {'x': 1}
    assert llm.provider == 'gigachat'
    assert b.calls == 0


async def test_falls_back_to_yandexgpt() -> None:
    llm = LLMChain([_Fake('gigachat', fail=True), _Fake('yandexgpt', 'ответ {"x": 2} конец')])
    assert await llm.complete_json(system='s', user='u') == {'x': 2}
    assert llm.provider == 'yandexgpt'


async def test_bad_json_tries_next_and_skips_unconfigured() -> None:
    off = _Fake('gigachat', '{"x": 0}', configured=False)
    llm = LLMChain([off, _Fake('yandexgpt', 'без json'), _Fake('third', '{"x": 3}')])
    assert await llm.complete_json(system='s', user='u') == {'x': 3}
    assert off.calls == 0


async def test_all_fail_raises_for_rules_fallback() -> None:
    llm = LLMChain([_Fake('gigachat', fail=True)])
    assert llm.is_configured
    with pytest.raises(LLMProviderUnavailable):
        await llm.complete(system='s', user='u')
    assert not LLMChain([_Fake('gigachat', configured=False)]).is_configured


_REAL_CLIENT = httpx.AsyncClient


def _yandex(monkeypatch: pytest.MonkeyPatch, handler: Any) -> yandexgpt.YandexGPTClient:

    def factory(**kw: Any) -> httpx.AsyncClient:
        kw.pop('transport', None)
        return _REAL_CLIENT(transport=httpx.MockTransport(handler), **kw)

    monkeypatch.setattr(yandexgpt.httpx, 'AsyncClient', factory)
    client = yandexgpt.YandexGPTClient()
    client._key, client._folder = 'key', 'folder'
    return client


async def test_yandexgpt_request_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def ok(request: httpx.Request) -> httpx.Response:
        seen['auth'] = request.headers['authorization']
        seen['body'] = request.read().decode()
        return httpx.Response(200, json={'result': {'alternatives': [{'message': {'text': 'Москва'}}]}})

    client = _yandex(monkeypatch, ok)
    assert await client.complete(system='s', user='Столица?') == 'Москва'
    assert seen['auth'] == 'Api-Key key'
    assert 'gpt://folder/yandexgpt-lite/latest' in seen['body']

    denied = _yandex(monkeypatch, lambda r: httpx.Response(401, json={'error': 'no'}))
    with pytest.raises(LLMAuthError):
        await denied.complete(system='s', user='u')
    down = _yandex(monkeypatch, lambda r: httpx.Response(500, text='oops'))
    with pytest.raises(LLMProviderUnavailable):
        await down.complete(system='s', user='u')


async def test_status_endpoint(auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = [_Fake('gigachat', fail=True), _Fake('yandexgpt', 'ok'), _Fake('third', configured=False)]
    monkeypatch.setattr(chain, '_registry', lambda: {f.name: (lambda f=f: f) for f in fakes})
    monkeypatch.setattr(chain, '_status_cache', None)
    monkeypatch.setattr(chain.get_settings(), 'llm_providers', 'gigachat,yandexgpt,third')
    r = await auth_client.get('/api/v1/llm/status')
    assert r.status_code == 200
    body = r.json()
    assert body['active'] == 'yandexgpt'
    rows = {p['provider']: p for p in body['providers']}
    assert rows['gigachat']['ok'] is False
    assert 'LLMProviderUnavailable' in rows['gigachat']['error']
    assert rows['third']['configured'] is False


async def test_status_requires_auth(client: AsyncClient) -> None:
    r = await client.get('/api/v1/llm/status')
    assert r.status_code == 401
