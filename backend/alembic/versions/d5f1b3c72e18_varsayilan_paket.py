"""varsayilan_paket

Paket tablosu bossa "Aylik 8 Ders" varsayilan paketini ekler.

Revision ID: d5f1b3c72e18
Revises: c4e8a2b61d07
Create Date: 2026-10-25 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5f1b3c72e18'
down_revision: Union[str, None] = 'c4e8a2b61d07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO paket (id, ad, tur, ders_sayisi, sure_ay, varsayilan_fiyat, aktif) "
            "SELECT gen_random_uuid(), 'Aylık 8 Ders', 'aylik', 8, 1, 3400.00, true "
            "WHERE NOT EXISTS (SELECT 1 FROM paket)"
        )
    )


def downgrade() -> None:
    # Veri migrasyonu: kullanici verisi silinmez.
    pass
