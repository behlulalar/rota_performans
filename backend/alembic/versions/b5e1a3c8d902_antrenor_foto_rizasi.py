"""antrenor foto rizasi

Kalıcı rıza kaydı; mevcut fotoğraflı antrenörler için aktif rıza geri doldurulur.

Revision ID: b5e1a3c8d902
Revises: a4d9c2b7e015
Create Date: 2026-11-21 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'b5e1a3c8d902'
down_revision: Union[str, None] = 'a4d9c2b7e015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'antrenor_foto_rizasi',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('antrenor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('verildi', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('geri_cekildi', sa.DateTime(timezone=True), nullable=True),
        sa.Column('kaydeden_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('geri_ceken_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['antrenor_id'], ['antrenor.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kaydeden_id'], ['kullanici.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['geri_ceken_id'], ['kullanici.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_antrenor_foto_rizasi_antrenor_id'), 'antrenor_foto_rizasi', ['antrenor_id'], unique=False)
    op.create_index(
        'uq_antrenor_foto_rizasi_aktif', 'antrenor_foto_rizasi', ['antrenor_id'], unique=True,
        postgresql_where=sa.text('geri_cekildi IS NULL'),
    )
    op.execute(
        "INSERT INTO antrenor_foto_rizasi (id, antrenor_id) "
        "SELECT gen_random_uuid(), id FROM antrenor WHERE foto_anahtar IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index('uq_antrenor_foto_rizasi_aktif', table_name='antrenor_foto_rizasi')
    op.drop_index(op.f('ix_antrenor_foto_rizasi_antrenor_id'), table_name='antrenor_foto_rizasi')
    op.drop_table('antrenor_foto_rizasi')
