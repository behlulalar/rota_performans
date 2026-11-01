"""kulup_instagram

Revision ID: b5e2c8d41f07
Revises: e8b4d6f21a53
Create Date: 2026-11-01 10:00:00.000000

Kulüp ayarlarına Instagram kullanıcı adı (veli paneli ve giriş sayfasında "takip edin" bağlantısı).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'b5e2c8d41f07'
down_revision: Union[str, None] = 'e8b4d6f21a53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('kulup_ayari', sa.Column('instagram', sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column('kulup_ayari', 'instagram')
