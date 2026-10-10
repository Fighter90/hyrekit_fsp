"""Статус LLM-провайдеров: настроен ли ключ и отвечает ли модель."""

from typing import Any

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.llm import chain

router = APIRouter(prefix='/llm', tags=['LLM'])


@router.get('/status', summary='Статус GigaChat и YandexGPT (проверочный запрос, кэш 5 минут)')
async def llm_status(_user: Any = Depends(get_current_user)) -> dict[str, Any]:
    providers = await chain.status()
    active = next((p['provider'] for p in providers if p['ok']), None)
    return {'active': active, 'fallback': 'rules' if active is None else None, 'providers': providers}
