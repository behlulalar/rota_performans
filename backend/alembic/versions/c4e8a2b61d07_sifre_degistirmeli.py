"""kullanici.sifre_degistirmeli

Gecici sifreyle acilan hesaplarda ilk giriste sifre degistirmeyi zorunlu kilar.

Revision ID: c4e8a2b61d07
Revises: b7d2f4a91c35
Create Date: 2026-10-25 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e8a2b61d07'
down_revision: Union[str, None] = 'b7d2f4a91c35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'kullanici',
        sa.Column('sifre_degistirmeli', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )


def downgrade() -> None:
    op.drop_column('kullanici', 'sifre_degistirmeli')
