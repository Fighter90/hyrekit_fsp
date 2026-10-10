"""Экспресс-тест для жюри: гостевой кандидат и режим попытки (FSP-32).

0001 строит схему из текущих моделей, поэтому на свежей базе колонки уже
есть; добавляем их только там, где база создана раньше.

Revision ID: 0003_express_test
Revises: 0002_consents_favorites
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0003_express_test'
down_revision: str | None = '0002_consents_favorites'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = [
    ('candidate_profiles', sa.Column('is_guest', sa.Boolean(), nullable=False, server_default=sa.false())),
    ('assessment_attempts', sa.Column('mode', sa.String(16), nullable=False, server_default='full')),
]


def _has(table: str, column: str) -> bool:
    return column in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for table, column in COLUMNS:
        if not _has(table, column.name):
            op.add_column(table, column)


def downgrade() -> None:
    for table, column in COLUMNS:
        if _has(table, column.name):
            with op.batch_alter_table(table) as batch:
                batch.drop_column(column.name)
