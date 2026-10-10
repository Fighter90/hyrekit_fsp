"""Цепочка LLM-провайдеров: GigaChat, затем YandexGPT, затем правила у вызывающего.

Порядок задаёт `LLM_PROVIDERS`. Первый настроенный и ответивший провайдер
даёт результат, его имя остаётся в `provider` — так разбор показывает, кто
его написал. Если не ответил никто, поднимается `LLMProviderUnavailable`, и
вызывающий код переходит на детерминированные правила.
"""

from __future__ import annotations

import ast
import json
import logging
import re
import time
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.exceptions import LLMProviderUnavailable, LLMResponseError

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r'\{.*\}', re.S)
_FENCE = re.compile(r'```(?:json)?\s*(.*?)```', re.S)
_TRAILING_COMMA = re.compile(r',\s*([}\]])')
PING_TTL = 300  # статус провайдеров кэшируется на 5 минут

# Последняя ошибка каждого провайдера в рабочих запросах: проверочный запрос
# статуса короткий и проходит, а разбор кода может ломаться на формате ответа.
last_errors: dict[str, dict[str, Any]] = {}


class Provider(Protocol):
    name: str
    title: str

    @property
    def is_configured(self) -> bool: ...

    async def complete(self, *, system: str, user: str, temperature: float = 0.2, max_tokens: int = 2048) -> str: ...


def _loads(text: str) -> Any:
    """JSON модели с типичными огрехами: перевод строки внутри строки, лишняя запятая, одинарные кавычки."""
    for candidate in (text, _TRAILING_COMMA.sub(r'\1', text)):
        try:
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            pass
    try:
        return ast.literal_eval(_TRAILING_COMMA.sub(r'\1', text))
    except (ValueError, SyntaxError) as exc:
        raise json.JSONDecodeError(str(exc), text, 0) from exc


def parse_json(raw: str, title: str) -> dict[str, Any]:
    fenced = _FENCE.search(raw)
    match = _JSON_BLOCK.search(fenced.group(1) if fenced else raw)
    if not match:
        raise LLMResponseError(f'{title} вернул ответ без JSON')
    try:
        data = _loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f'{title} вернул некорректный JSON') from exc
    if not isinstance(data, dict):
        raise LLMResponseError('Ожидался JSON-объект')
    return data


def _reason(exc: Exception) -> str:
    text = getattr(exc, 'detail', None) or getattr(exc, 'message', None) or str(exc)
    return f'{type(exc).__name__}: {text}'[:200]


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
            raw = ''
            try:
                raw = await p.complete(system=system, user=user, temperature=temperature, max_tokens=max_tokens)
                data = parse_json(raw, p.title) if as_json else {}
            except Exception as exc:  # следующий провайдер
                reason = _reason(exc)
                logger.warning('LLM %s не ответил: %s', p.name, reason)
                if raw:
                    logger.warning('Ответ %s: %.300s', p.name, raw)
                last_errors[p.name] = {'error': reason, 'at': time.time()}
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
                row['error'] = _reason(exc)
            row['latency_ms'] = round((time.monotonic() - started) * 1000)
        out.append(row)
    for row in out:
        if row['provider'] in last_errors:
            row['last_error'] = last_errors[row['provider']]['error']
    _status_cache = (time.monotonic() + PING_TTL, out)
    return out


def get_llm() -> LLMChain:
    """Фабрика цепочки (удобно подменять в тестах)."""
    return LLMChain()
