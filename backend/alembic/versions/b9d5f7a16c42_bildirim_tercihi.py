"""bildirim tercihi

Revision ID: b9d5f7a16c42
Revises: a8c4e6f05b31
Create Date: 2026-10-29 14:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'b9d5f7a16c42'
down_revision: Union[str, None] = 'a8c4e6f05b31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bildirim_tercihi',
        sa.Column('kullanici_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('whatsapp', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('push', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('ders_gelmedi', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('ders_hakki', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('guncelleme', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['kullanici_id'], ['kullanici.id'], name=op.f('fk_bildirim_tercihi_kullanici_id_kullanici'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('kullanici_id', name=op.f('pk_bildirim_tercihi')),
    )


def downgrade() -> None:
    op.drop_table('bildirim_tercihi')
