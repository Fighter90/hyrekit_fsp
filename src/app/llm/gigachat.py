"""Асинхронный клиент GigaChat.

Используется для разбора резюме, генерации формулировок заданий и
объяснения выдачи. Если ключ GIGACHAT_CREDENTIALS не задан, клиент
сообщает об этом через `is_configured`, и вызывающий код переходит на
детерминированный (rule-based) режим: демо и тесты работают без сети.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import LLMAuthError, LLMProviderUnavailable, LLMResponseError

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r'\{.*\}', re.S)


class GigaChatClient:
    """Тонкая обёртка над официальным SDK `gigachat`."""

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self._credentials = settings.gigachat_credentials
        self._scope = settings.gigachat_scope
        self._model = model or settings.gigachat_model
        self._client: Any = None

    @property
    def is_configured(self) -> bool:
        return bool(self._credentials)

    def _get_client(self) -> Any:
        if self._client is None:
            from gigachat import GigaChat

            self._client = GigaChat(
                credentials=self._credentials,
                scope=self._scope,
                model=self._model,
                verify_ssl_certs=False,
            )
        return self._client

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """Один запрос system+user → текст ответа."""
        if not self.is_configured:
            raise LLMProviderUnavailable('gigachat')

        from gigachat.models import Chat, Messages, MessagesRole

        payload = Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM, content=system),
                Messages(role=MessagesRole.USER, content=user),
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            response = await self._get_client().achat(payload)
        except Exception as exc:
            text = str(exc)
            logger.error('GigaChat error: %s', text[:300])
            if '401' in text or 'Unauthorized' in text:
                raise LLMAuthError('gigachat') from exc
            raise LLMProviderUnavailable('gigachat') from exc
        return str(response.choices[0].message.content)

    async def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        """Запрос, ответ на который обязан быть JSON-объектом."""
        raw = await self.complete(system=system, user=user)
        match = _JSON_BLOCK.search(raw)
        if not match:
            raise LLMResponseError('GigaChat вернул ответ без JSON')
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMResponseError('GigaChat вернул некорректный JSON') from exc
        if not isinstance(data, dict):
            raise LLMResponseError('Ожидался JSON-объект')
        return data


def get_llm() -> GigaChatClient:
    """Фабрика клиента (удобно подменять в тестах)."""
    return GigaChatClient()
