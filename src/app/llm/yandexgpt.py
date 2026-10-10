"""Клиент YandexGPT (Yandex AI Studio, Foundation Models API).

Резервный провайдер: вызывается, если GigaChat не настроен или не ответил.
Ключ — API-ключ сервисного аккаунта (`YANDEX_GPT_API_KEY`) с ролью
`ai.languageModels.user` в каталоге `YANDEX_GPT_FOLDER_ID`.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.core.exceptions import LLMAuthError, LLMProviderUnavailable, LLMResponseError

logger = logging.getLogger(__name__)

URL = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
TIMEOUT = 60


class YandexGPTClient:
    name = 'yandexgpt'
    title = 'YandexGPT'

    def __init__(self) -> None:
        s = get_settings()
        self._key = s.yandex_gpt_api_key
        self._folder = s.yandex_gpt_folder_id
        self._model = s.yandex_gpt_model

    @property
    def is_configured(self) -> bool:
        return bool(self._key and self._folder)

    async def complete(self, *, system: str, user: str, temperature: float = 0.2, max_tokens: int = 2048) -> str:
        if not self.is_configured:
            raise LLMProviderUnavailable(self.name)
        body = {
            'modelUri': f'gpt://{self._folder}/{self._model}',
            'completionOptions': {'stream': False, 'temperature': temperature, 'maxTokens': str(max_tokens)},
            'messages': [{'role': 'system', 'text': system}, {'role': 'user', 'text': user}],
        }
        headers = {'Authorization': f'Api-Key {self._key}', 'x-folder-id': self._folder}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.post(URL, json=body, headers=headers)
        except httpx.HTTPError as exc:
            logger.error('YandexGPT недоступен: %s', exc)
            raise LLMProviderUnavailable(self.name) from exc
        if r.status_code in (401, 403):
            logger.error('YandexGPT отклонил ключ: HTTP %s %s', r.status_code, r.text[:200])
            raise LLMAuthError(self.name)
        if r.status_code != 200:
            logger.error('YandexGPT: HTTP %s %s', r.status_code, r.text[:300])
            raise LLMProviderUnavailable(self.name)
        try:
            return str(r.json()['result']['alternatives'][0]['message']['text'])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMResponseError('YandexGPT вернул ответ неизвестного формата') from exc
