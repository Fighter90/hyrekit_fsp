"""Arena фиксирует отправку до проверки (commit), поэтому откат тестовой сессии
её не убирает. После каждого теста Arena база очищается целиком, чтобы данные
не попадали в другие модули тестов."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base


@pytest.fixture(autouse=True)
async def _wipe_committed(session: AsyncSession) -> AsyncIterator[None]:
    yield
    await session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        await session.execute(table.delete())
    await session.commit()
