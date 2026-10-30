"""destek_ikili_dogrulama

Revision ID: e8b4d6f21a53
Revises: a3c9e5b71d04
Create Date: 2026-10-30 10:00:00.000000

Rol sütunu CHECK'siz VARCHAR(16) olduğu için yeni "destek" rolü şema değişikliği gerektirmez;
yalnız TOTP alanları eklenir.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'e8b4d6f21a53'
down_revision: Union[str, None] = 'a3c9e5b71d04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('kullanici', sa.Column('totp_sifreli', sa.LargeBinary(), nullable=True))
    op.add_column('kullanici', sa.Column('totp_aktif', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('kullanici', sa.Column('totp_kurtarma', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Eski sürümde destek rolü yok: kayıtlar silinmez (başka tablolara bağlı olabilir), pasif yönetici olarak kalır.
    op.execute("UPDATE kullanici SET rol = 'admin', aktif = false WHERE rol = 'destek'")
    op.drop_column('kullanici', 'totp_kurtarma')
    op.drop_column('kullanici', 'totp_aktif')
    op.drop_column('kullanici', 'totp_sifreli')
