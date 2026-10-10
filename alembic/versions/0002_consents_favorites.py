"""Журнал согласий кандидата и избранное работодателя.

Таблицы создаются с checkfirst: на чистой базе их уже создаёт 0001 из моделей,
на базе с 0001 предыдущей версии миграция добавляет только их.

Revision ID: 0002_consents_favorites
Revises: 0001_initial_schema
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.candidates.models import ConsentEvent
from app.employers.models import Favorite

revision: str = '0002_consents_favorites'
down_revision: str | None = '0001_initial_schema'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = [ConsentEvent.__table__, Favorite.__table__]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
