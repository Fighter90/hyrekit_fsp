"""Разграничение доступа по ролям личных кабинетов."""

from __future__ import annotations

from fastapi import Depends

from app.auth.models import User, UserRole
from app.core.dependencies import get_current_user
from app.core.exceptions import Forbidden


async def require_candidate(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.CANDIDATE:
        raise Forbidden('Раздел доступен только кандидатам')
    return user


async def require_employer(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.EMPLOYER:
        raise Forbidden('Раздел доступен только работодателям')
    return user
