"""ek ders katilim

Telafi planı tablosu ders katılım planına genişler (tur: telafi / ek_ders); yoklamaya ek_ders_mi eklenir.
Mevcut tüm planlar telafidir. Ek ders ücretsizdir: defteri etkilemez.

Revision ID: c3f7a9d1e284
Revises: b5e1a3c8d902
Create Date: 2026-11-21 15:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c3f7a9d1e284'
down_revision: Union[str, None] = 'b5e1a3c8d902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('telafi_plani', sa.Column('tur', sa.String(length=24), server_default='telafi', nullable=False))
    op.create_check_constraint(op.f('ck_telafi_plani_katilimturu'), 'telafi_plani', "tur IN ('telafi', 'ek_ders')")
    op.add_column('yoklama', sa.Column('ek_ders_mi', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.create_check_constraint(op.f('ck_yoklama_ek_ders_telafi_ayri'), 'yoklama', 'NOT (telafi_mi AND ek_ders_mi)')
    # Telafi/ek ders planlama bildirimleri ayrı tercih kategorisi; mevcut hesaplar için varsayılan açık.
    op.add_column('bildirim_tercihi', sa.Column('ders_plani', sa.Boolean(), server_default=sa.text('true'), nullable=False))


def downgrade() -> None:
    bagli = op.get_bind()
    var = bagli.execute(
        sa.text(
            "SELECT (SELECT count(*) FROM telafi_plani WHERE tur = 'ek_ders') "
            "+ (SELECT count(*) FROM yoklama WHERE ek_ders_mi)"
        )
    ).scalar_one()
    if var:
        raise RuntimeError("Ek ders kayıtları var; geri alma veri kaybettirir")
    op.drop_column('bildirim_tercihi', 'ders_plani')
    op.drop_constraint(op.f('ck_yoklama_ek_ders_telafi_ayri'), 'yoklama', type_='check')
    op.drop_column('yoklama', 'ek_ders_mi')
    op.drop_constraint(op.f('ck_telafi_plani_katilimturu'), 'telafi_plani', type_='check')
    op.drop_column('telafi_plani', 'tur')
