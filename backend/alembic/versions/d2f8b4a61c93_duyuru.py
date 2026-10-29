"""duyuru

Revision ID: d2f8b4a61c93
Revises: c1e7a9b35d28
Create Date: 2026-10-29 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'd2f8b4a61c93'
down_revision: Union[str, None] = 'c1e7a9b35d28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'duyuru',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('baslik', sa.String(length=120), nullable=False),
        sa.Column('metin', sa.Text(), nullable=False),
        sa.Column('hedef_tur', sa.Enum('oturum', 'grup', 'tum', name='duyuruhedeftur', native_enum=False, length=24, create_constraint=True), nullable=False),
        sa.Column('hedef', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('kanal_push', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('kanal_whatsapp', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('olusturan_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('oturum_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('olusturma', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['olusturan_id'], ['kullanici.id'], name=op.f('fk_duyuru_olusturan_id_kullanici'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['oturum_id'], ['ders_oturumu.id'], name=op.f('fk_duyuru_oturum_id_ders_oturumu'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_duyuru')),
    )
    op.create_index(op.f('ix_duyuru_oturum_id'), 'duyuru', ['oturum_id'], unique=False)

    op.add_column('bildirim', sa.Column('duyuru_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(op.f('fk_bildirim_duyuru_id_duyuru'), 'bildirim', 'duyuru', ['duyuru_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_bildirim_duyuru_id'), 'bildirim', ['duyuru_id'], unique=False)
    op.create_index(
        'uq_bildirim_duyuru_alici_kanal', 'bildirim', ['duyuru_id', 'alici_iletisim_id', 'kanal'],
        unique=True, postgresql_where=sa.text('duyuru_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_bildirim_duyuru_alici_kanal', table_name='bildirim', postgresql_where=sa.text('duyuru_id IS NOT NULL'))
    op.drop_index(op.f('ix_bildirim_duyuru_id'), table_name='bildirim')
    op.drop_constraint(op.f('fk_bildirim_duyuru_id_duyuru'), 'bildirim', type_='foreignkey')
    op.drop_column('bildirim', 'duyuru_id')
    op.drop_index(op.f('ix_duyuru_oturum_id'), table_name='duyuru')
    op.drop_table('duyuru')
