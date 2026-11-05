"""whatsapp gonderim ayarlari

Revision ID: c7a1e3f95b26
Revises: af728a270c05
Create Date: 2026-11-05 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c7a1e3f95b26'
down_revision: Union[str, None] = 'af728a270c05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('kulup_ayari', sa.Column('wa_saatlik_limit', sa.Integer(), server_default=sa.text('50'), nullable=False))
    op.add_column('kulup_ayari', sa.Column('wa_gunluk_limit', sa.Integer(), server_default=sa.text('250'), nullable=False))
    op.add_column('kulup_ayari', sa.Column('wa_baslangic_saat', sa.Integer(), server_default=sa.text('9'), nullable=False))
    op.add_column('kulup_ayari', sa.Column('wa_bitis_saat', sa.Integer(), server_default=sa.text('21'), nullable=False))
    op.add_column('kulup_ayari', sa.Column('wa_push_varsa_atla', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.create_check_constraint(op.f('ck_kulup_ayari_wa_saatlik_limit_aralik'), 'kulup_ayari', 'wa_saatlik_limit BETWEEN 1 AND 200')
    op.create_check_constraint(op.f('ck_kulup_ayari_wa_gunluk_limit_aralik'), 'kulup_ayari', 'wa_gunluk_limit BETWEEN 1 AND 1000')
    op.create_check_constraint(op.f('ck_kulup_ayari_wa_baslangic_saat_aralik'), 'kulup_ayari', 'wa_baslangic_saat BETWEEN 0 AND 23')
    op.create_check_constraint(op.f('ck_kulup_ayari_wa_bitis_saat_aralik'), 'kulup_ayari', 'wa_bitis_saat BETWEEN 1 AND 24')
    op.create_check_constraint(op.f('ck_kulup_ayari_wa_saat_sirasi'), 'kulup_ayari', 'wa_baslangic_saat < wa_bitis_saat')
    op.add_column('duyuru', sa.Column('her_iki_kanal', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('duyuru', 'her_iki_kanal')
    for ad in ('wa_saat_sirasi', 'wa_bitis_saat_aralik', 'wa_baslangic_saat_aralik', 'wa_gunluk_limit_aralik', 'wa_saatlik_limit_aralik'):
        op.drop_constraint(op.f(f'ck_kulup_ayari_{ad}'), 'kulup_ayari', type_='check')
    for kolon in ('wa_push_varsa_atla', 'wa_bitis_saat', 'wa_baslangic_saat', 'wa_gunluk_limit', 'wa_saatlik_limit'):
        op.drop_column('kulup_ayari', kolon)
