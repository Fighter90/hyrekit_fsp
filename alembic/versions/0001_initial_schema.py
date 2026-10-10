"""Начальная схема HyreKit.

Схема строится из SQLAlchemy-моделей (единый источник правды), что исключает
расхождение между кодом и миграцией на этапе MVP. Последующие изменения
оформляются обычными инкрементальными миграциями.

Revision ID: 0001_initial_schema
Revises: None
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

import app.models  # noqa: F401  — регистрация всех моделей в Base.metadata
from app.core.database import Base

revision: str = '0001_initial_schema'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
