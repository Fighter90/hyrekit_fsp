"""Цепочка LLM-провайдеров: GigaChat, затем YandexGPT, затем правила у вызывающего.

Порядок задаёт `LLM_PROVIDERS`. Первый настроенный и ответивший провайдер
даёт результат, его имя остаётся в `provider` — так разбор показывает, кто
его написал. Если не ответил никто, поднимается `LLMProviderUnavailable`, и
вызывающий код переходит на детерминированные правила.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.exceptions import LLMProviderUnavailable, LLMResponseError

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r'\{.*\}', re.S)
PING_TTL = 300  # статус провайдеров кэшируется на 5 минут


class Provider(Protocol):
    name: str
    title: str

    @property
    def is_configured(self) -> bool: ...

    async def complete(self, *, system: str, user: str, temperature: float = 0.2, max_tokens: int = 2048) -> str: ...


def parse_json(raw: str, title: str) -> dict[str, Any]:
    match = _JSON_BLOCK.search(raw)
    if not match:
        raise LLMResponseError(f'{title} вернул ответ без JSON')
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f'{title} вернул некорректный JSON') from exc
    if not isinstance(data, dict):
        raise LLMResponseError('Ожидался JSON-объект')
    return data


def _registry() -> dict[str, type]:
    from app.llm.gigachat import GigaChatClient
    from app.llm.yandexgpt import YandexGPTClient

    return {'gigachat': GigaChatClient, 'yandexgpt': YandexGPTClient}


class LLMChain:
    def __init__(self, providers: list[Provider] | None = None) -> None:
        if providers is None:
            known = _registry()
            order = [n.strip() for n in get_settings().llm_providers.split(',') if n.strip()]
            providers = [known[n]() for n in order if n in known]
        self.providers = providers
        self.provider: str | None = None  # кто ответил на последний запрос

    @property
    def is_configured(self) -> bool:
        return any(p.is_configured for p in self.providers)

    async def complete(self, *, system: str, user: str, temperature: float = 0.2, max_tokens: int = 2048) -> str:
        return (await self._run(system, user, temperature, max_tokens, as_json=False))[0]

    async def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        return (await self._run(system, user, 0.2, 2048, as_json=True))[1]

    async def _run(
        self, system: str, user: str, temperature: float, max_tokens: int, *, as_json: bool
    ) -> tuple[str, dict[str, Any]]:
        last: Exception | None = None
        for p in self.providers:
            if not p.is_configured:
                continue
            try:
                raw = await p.complete(system=system, user=user, temperature=temperature, max_tokens=max_tokens)
                data = parse_json(raw, p.title) if as_json else {}
            except Exception as exc:  # следующий провайдер
                logger.warning('LLM %s не ответил: %s', p.name, exc)
                last = exc
                continue
            self.provider = p.name
            return raw, data
        raise LLMProviderUnavailable('llm') from last


_status_cache: tuple[float, list[dict[str, Any]]] | None = None


async def status(force: bool = False) -> list[dict[str, Any]]:
    """Проверка провайдеров коротким запросом: настроен ли, отвечает ли, причина отказа."""
    global _status_cache
    if _status_cache and not force and _status_cache[0] > time.monotonic():
        return _status_cache[1]
    out = []
    for p in LLMChain().providers:
        row: dict[str, Any] = {'provider': p.name, 'title': p.title, 'configured': p.is_configured, 'ok': False}
        if p.is_configured:
            started = time.monotonic()
            try:
                await p.complete(system='Отвечай одним словом.', user='Ответь: ok', max_tokens=10)
                row['ok'] = True
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {getattr(exc, "message", str(exc))}'[:200]
            row['latency_ms'] = round((time.monotonic() - started) * 1000)
        out.append(row)
    _status_cache = (time.monotonic() + PING_TTL, out)
    return out


def get_llm() -> LLMChain:
    """Фабрика цепочки (удобно подменять в тестах)."""
    return LLMChain()
