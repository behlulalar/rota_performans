"""odeme_iptali

Odeme iptal alanlari; defterde paket yuklemesinin odemeye baglanmasi ve tekil indeksin
"odeme basina bir yukleme" olarak degistirilmesi (iptal edilen odeme yeniden alinabilsin).

Revision ID: e6a2c4d83f19
Revises: d5f1b3c72e18
Create Date: 2026-10-25 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e6a2c4d83f19'
down_revision: Union[str, None] = 'd5f1b3c72e18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('odeme', sa.Column('iptal_zamani', sa.DateTime(timezone=True), nullable=True))
    op.add_column('odeme', sa.Column('iptal_nedeni', sa.Text(), nullable=True))
    op.add_column('odeme', sa.Column('iptal_eden_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f('fk_odeme_iptal_eden_id_kullanici'), 'odeme', 'kullanici', ['iptal_eden_id'], ['id'], ondelete='SET NULL'
    )
    op.create_check_constraint(
        op.f('ck_odeme_iptal_alanlari_birlikte'), 'odeme', '(iptal_zamani IS NULL) = (iptal_nedeni IS NULL)'
    )

    op.add_column('ders_hakki_hareketi', sa.Column('odeme_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f('fk_ders_hakki_hareketi_odeme_id_odeme'), 'ders_hakki_hareketi', 'odeme', ['odeme_id'], ['id'],
        ondelete='RESTRICT',
    )
    op.create_index('ix_ders_hakki_hareketi_odeme_id', 'ders_hakki_hareketi', ['odeme_id'])
    op.drop_index('uq_hareket_paket_yuklemesi', table_name='ders_hakki_hareketi')
    op.create_index(
        'uq_hareket_paket_yuklemesi', 'ders_hakki_hareketi', ['ogrenci_paketi_id'], unique=True,
        postgresql_where=sa.text("tur = 'paket_yuklemesi' AND odeme_id IS NULL"),
    )
    op.create_index(
        'uq_hareket_odeme_yuklemesi', 'ders_hakki_hareketi', ['odeme_id'], unique=True,
        postgresql_where=sa.text("tur = 'paket_yuklemesi' AND odeme_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index('uq_hareket_odeme_yuklemesi', table_name='ders_hakki_hareketi')
    op.drop_index('uq_hareket_paket_yuklemesi', table_name='ders_hakki_hareketi')
    op.create_index(
        'uq_hareket_paket_yuklemesi', 'ders_hakki_hareketi', ['ogrenci_paketi_id'], unique=True,
        postgresql_where=sa.text("tur = 'paket_yuklemesi'"),
    )
    op.drop_index('ix_ders_hakki_hareketi_odeme_id', table_name='ders_hakki_hareketi')
    op.drop_constraint(op.f('fk_ders_hakki_hareketi_odeme_id_odeme'), 'ders_hakki_hareketi', type_='foreignkey')
    op.drop_column('ders_hakki_hareketi', 'odeme_id')
    op.drop_constraint(op.f('ck_odeme_iptal_alanlari_birlikte'), 'odeme', type_='check')
    op.drop_constraint(op.f('fk_odeme_iptal_eden_id_kullanici'), 'odeme', type_='foreignkey')
    op.drop_column('odeme', 'iptal_eden_id')
    op.drop_column('odeme', 'iptal_nedeni')
    op.drop_column('odeme', 'iptal_zamani')
