"""kulup ayari

Revision ID: c1e7a9b35d28
Revises: b9d5f7a16c42
Create Date: 2026-10-29 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c1e7a9b35d28'
down_revision: Union[str, None] = 'b9d5f7a16c42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'kulup_ayari',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ad', sa.String(length=120), server_default='Rota Performans Akademi', nullable=False),
        sa.Column('telefon', sa.String(length=20), nullable=True),
        sa.Column('eposta', sa.String(length=254), nullable=True),
        sa.Column('adres', sa.String(length=500), nullable=True),
        sa.Column('geri_alma_dakika', sa.Integer(), server_default=sa.text('3'), nullable=False),
        sa.Column('azaldi_esigi', sa.Integer(), server_default=sa.text('2'), nullable=False),
        sa.Column('guncelleme', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('id = 1', name=op.f('ck_kulup_ayari_tek_satir')),
        sa.CheckConstraint('geri_alma_dakika BETWEEN 1 AND 15', name=op.f('ck_kulup_ayari_geri_alma_aralik')),
        sa.CheckConstraint('azaldi_esigi BETWEEN 1 AND 5', name=op.f('ck_kulup_ayari_azaldi_esigi_aralik')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_kulup_ayari')),
    )


def downgrade() -> None:
    op.drop_table('kulup_ayari')
