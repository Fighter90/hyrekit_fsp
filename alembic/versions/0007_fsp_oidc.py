"""Вход и привязка через ФСП ID (FSP-20): `candidate_profiles.fsp_sub`.

0001 строит схему из текущих моделей, поэтому на свежей базе колонка уже
есть; добавляем её только там, где база создана раньше.

Revision ID: 0007_fsp_oidc
Revises: 0006_item_calibration
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0007_fsp_oidc'
down_revision: str | None = '0006_item_calibration'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX = 'ix_candidate_profiles_fsp_sub'


def _has(table: str, column: str) -> bool:
    return column in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has('candidate_profiles', 'fsp_sub'):
        op.add_column('candidate_profiles', sa.Column('fsp_sub', sa.String(255), nullable=True))
        op.create_index(INDEX, 'candidate_profiles', ['fsp_sub'], unique=True)


def downgrade() -> None:
    if _has('candidate_profiles', 'fsp_sub'):
        op.drop_index(INDEX, table_name='candidate_profiles')
        with op.batch_alter_table('candidate_profiles') as batch:
            batch.drop_column('fsp_sub')
