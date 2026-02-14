"""Baseline: текущая схема БД

Revision ID: 001
Revises: None
Create Date: 2026-02-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline — все таблицы уже созданы через create_all()
    # Эта миграция только фиксирует начальную точку для Alembic
    pass


def downgrade() -> None:
    pass
