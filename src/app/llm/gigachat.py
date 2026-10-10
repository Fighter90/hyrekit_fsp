"""Асинхронный клиент GigaChat.

Используется для разбора резюме, генерации формулировок заданий и
объяснения выдачи. Если ключ GIGACHAT_CREDENTIALS не задан, клиент
сообщает об этом через `is_configured`, и вызывающий код переходит на
детерминированный (rule-based) режим: демо и тесты работают без сети.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import LLMAuthError, LLMProviderUnavailable, LLMResponseError

logger = logging.getLogger(__name__)


class GigaChatClient:
    """Тонкая обёртка над официальным SDK `gigachat`."""

    name = 'gigachat'
    title = 'GigaChat'

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
        choice = response.choices[0]
        if getattr(choice, 'finish_reason', None) == 'blacklist':
            # тематический фильтр GigaChat: текст ответа — шаблонный отказ
            raise LLMResponseError('GigaChat отказался отвечать (тематический фильтр)')
        return str(choice.message.content)

    async def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        """Запрос, ответ на который обязан быть JSON-объектом."""
        from app.llm.chain import parse_json

        return parse_json(await self.complete(system=system, user=user), self.title)


def get_llm() -> Any:
    """Цепочка провайдеров: GigaChat, затем YandexGPT (см. `app.llm.chain`)."""
    from app.llm.chain import get_llm as chain

    return chain()
