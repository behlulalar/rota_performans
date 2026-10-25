"""ogrenci telefon

Revision ID: a1c3e5f70912
Revises: 446735099133
Create Date: 2026-10-25 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c3e5f70912'
down_revision: Union[str, None] = '446735099133'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ogrenci', sa.Column('telefon', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('ogrenci', 'telefon')
