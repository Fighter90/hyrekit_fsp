"""GET /catalog — публичный справочник."""

from __future__ import annotations

from fastapi import APIRouter

from app.catalog.data import public_catalog

router = APIRouter(prefix='/catalog', tags=['catalog'])


@router.get('', summary='Справочник специализаций, грейдов, отраслей')
async def get_catalog() -> dict:
    return public_catalog()
