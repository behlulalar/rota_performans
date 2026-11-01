"""manuel_kayit

Revision ID: af728a270c05
Revises: b5e2c8d41f07
Create Date: 2026-11-01 15:58:13.705192

Gelir raporu için öğrenci ödemesi dışındaki manuel gelir/gider kayıtları.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'af728a270c05'
down_revision: Union[str, None] = 'b5e2c8d41f07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('manuel_kayit',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tur', sa.Enum('gelir', 'gider', name='manuelkayitturu', native_enum=False, create_constraint=True, length=24), nullable=False),
    sa.Column('tarih', sa.Date(), nullable=False),
    sa.Column('tutar', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('yontem', sa.Enum('nakit', 'havale_eft', 'diger', name='odemeyontemi', native_enum=False, create_constraint=True, length=24), nullable=False),
    sa.Column('aciklama', sa.String(length=200), nullable=False),
    sa.Column('olusturan_id', sa.UUID(), nullable=True),
    sa.Column('olusturma', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('iptal_zamani', sa.DateTime(timezone=True), nullable=True),
    sa.Column('iptal_nedeni', sa.Text(), nullable=True),
    sa.Column('iptal_eden_id', sa.UUID(), nullable=True),
    sa.CheckConstraint('(iptal_zamani IS NULL) = (iptal_nedeni IS NULL)', name=op.f('ck_manuel_kayit_iptal_alanlari_birlikte')),
    sa.CheckConstraint('tutar > 0', name=op.f('ck_manuel_kayit_tutar_pozitif')),
    sa.ForeignKeyConstraint(['iptal_eden_id'], ['kullanici.id'], name=op.f('fk_manuel_kayit_iptal_eden_id_kullanici'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['olusturan_id'], ['kullanici.id'], name=op.f('fk_manuel_kayit_olusturan_id_kullanici'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_manuel_kayit'))
    )
    op.create_index(op.f('ix_manuel_kayit_tarih'), 'manuel_kayit', ['tarih'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_manuel_kayit_tarih'), table_name='manuel_kayit')
    op.drop_table('manuel_kayit')
