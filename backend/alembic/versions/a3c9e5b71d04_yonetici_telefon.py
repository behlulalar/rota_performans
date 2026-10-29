"""yonetici_telefon

Revision ID: a3c9e5b71d04
Revises: d2f8b4a61c93
Create Date: 2026-10-29 20:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a3c9e5b71d04'
down_revision: Union[str, None] = 'd2f8b4a61c93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('kullanici', sa.Column('telefon', sa.String(length=32), nullable=True))
    op.create_index(
        'uq_kullanici_telefon', 'kullanici', ['telefon'], unique=True,
        postgresql_where=sa.text('telefon IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_kullanici_telefon', table_name='kullanici', postgresql_where=sa.text('telefon IS NOT NULL'))
    op.drop_column('kullanici', 'telefon')
