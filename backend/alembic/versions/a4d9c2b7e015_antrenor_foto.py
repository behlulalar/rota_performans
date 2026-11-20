"""antrenor profil fotografi

Antrenöre `foto_anahtar` (yalnız yönetici yükler).

Revision ID: a4d9c2b7e015
Revises: a4d7c1e92b68
Create Date: 2026-11-20 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a4d9c2b7e015'
down_revision: Union[str, None] = 'a4d7c1e92b68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('antrenor', sa.Column('foto_anahtar', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('antrenor', 'foto_anahtar')
