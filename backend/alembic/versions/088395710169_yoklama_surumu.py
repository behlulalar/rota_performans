"""yoklama surumu

Revision ID: 088395710169
Revises: fa8de04c0f64
Create Date: 2026-10-24 16:51:13.257672
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '088395710169'
down_revision: Union[str, None] = 'fa8de04c0f64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('yoklama', sa.Column('surum', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('ders_hakki_hareketi', sa.Column('yoklama_surum', sa.Integer(), nullable=True))
    # Var olan yoklama hareketleri ilk sürüme (0) aittir. Defter tetikleyicisi UPDATE'i yasakladığı için
    # bu tek seferlik veri düzeltmesinde tetikleyici geçici olarak kapatılır.
    op.execute("ALTER TABLE ders_hakki_hareketi DISABLE TRIGGER ders_hakki_hareketi_degistirilemez")
    op.execute("UPDATE ders_hakki_hareketi SET yoklama_surum = 0 WHERE yoklama_id IS NOT NULL")
    op.execute("ALTER TABLE ders_hakki_hareketi ENABLE TRIGGER ders_hakki_hareketi_degistirilemez")
    op.create_check_constraint(
        op.f('ck_ders_hakki_hareketi_yoklama_surum_birlikte'),
        'ders_hakki_hareketi',
        '(yoklama_id IS NULL) = (yoklama_surum IS NULL)',
    )
    op.drop_index(op.f('uq_hareket_yoklama_tur_sayac'), table_name='ders_hakki_hareketi', postgresql_where="((yoklama_id IS NOT NULL) AND ((tur)::text <> 'iptal'::text))")
    op.create_index('uq_hareket_yoklama_surum_tur_sayac', 'ders_hakki_hareketi', ['yoklama_id', 'yoklama_surum', 'tur', 'sayac'], unique=True, postgresql_where=sa.text("yoklama_id IS NOT NULL AND tur <> 'iptal'"))


def downgrade() -> None:
    # Birden çok sürümü olan yoklamalar varsa eski tekil indeks oluşturulamaz.
    op.drop_index('uq_hareket_yoklama_surum_tur_sayac', table_name='ders_hakki_hareketi', postgresql_where=sa.text("yoklama_id IS NOT NULL AND tur <> 'iptal'"))
    op.create_index(op.f('uq_hareket_yoklama_tur_sayac'), 'ders_hakki_hareketi', ['yoklama_id', 'tur', 'sayac'], unique=True, postgresql_where="((yoklama_id IS NOT NULL) AND ((tur)::text <> 'iptal'::text))")
    op.drop_constraint(op.f('ck_ders_hakki_hareketi_yoklama_surum_birlikte'), 'ders_hakki_hareketi', type_='check')
    op.drop_column('ders_hakki_hareketi', 'yoklama_surum')
    op.drop_column('yoklama', 'surum')
