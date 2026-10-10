"""Code Arena: раунды, участия, отправки и рейтинг (FSP-36).

Таблицы создаются с checkfirst: на чистой базе их уже создаёт 0001 из моделей.

Revision ID: 0005_code_arena
Revises: 0004_strict_grade_cut
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.arena.models import ArenaParticipant, ArenaRating, ArenaRound, ArenaSubmission

revision: str = '0005_code_arena'
down_revision: str | None = '0004_strict_grade_cut'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = [ArenaRound.__table__, ArenaParticipant.__table__, ArenaSubmission.__table__, ArenaRating.__table__]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
