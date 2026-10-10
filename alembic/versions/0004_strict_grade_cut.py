"""Порог грейда поднят на 0.75 логита (FSP-61): пересчёт сохранённой способности.

cut(g) был g − 2.5, стал g − 1.75. Способность у профилей и попыток сдвигается
на ту же величину, чтобы положение кандидата относительно порога его грейда,
рейтинг в категории и соответствие в подборке не изменились.

Revision ID: 0004_strict_grade_cut
Revises: 0003_express_test
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = '0004_strict_grade_cut'
down_revision: str | None = '0003_express_test'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SHIFT = 0.75
TABLES = ('candidate_profiles', 'assessment_attempts')


def _shift(delta: float) -> None:
    for table in TABLES:
        op.execute(f'UPDATE {table} SET ability = ability + {delta} WHERE ability IS NOT NULL')  # noqa: S608


def upgrade() -> None:
    _shift(SHIFT)


def downgrade() -> None:
    _shift(-SHIFT)
