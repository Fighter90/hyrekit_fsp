"""Мониторинг утечек заданий: статус семейств по последней калибровке (FSP-33).

Таблица создаётся с checkfirst: на чистой базе её уже создаёт 0001 из моделей.

Revision ID: 0006_item_calibration
Revises: 0005_code_arena
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.assessment.models import ItemCalibration

revision: str = '0006_item_calibration'
down_revision: str | None = '0005_code_arena'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ItemCalibration.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    ItemCalibration.__table__.drop(bind=op.get_bind(), checkfirst=True)
