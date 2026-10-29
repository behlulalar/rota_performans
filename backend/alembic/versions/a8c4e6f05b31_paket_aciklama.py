"""paket aciklama

Revision ID: a8c4e6f05b31
Revises: f7b3d5e94a20
Create Date: 2026-10-29 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a8c4e6f05b31'
down_revision: Union[str, None] = 'f7b3d5e94a20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('paket', sa.Column('aciklama', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('paket', 'aciklama')
