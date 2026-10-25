"""pos odeme yontemini kaldir

Revision ID: f7b3d5e94a20
Revises: e6a2c4d83f19
Create Date: 2026-10-25 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f7b3d5e94a20'
down_revision: Union[str, None] = 'e6a2c4d83f19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Müşteride POS cihazı yok. Varsa (yalnızca örnek veri) POS ödemeleri havale/EFT'ye çevrilir.
    op.execute("UPDATE odeme SET yontem = 'havale_eft' WHERE yontem = 'pos'")
    op.drop_constraint('odemeyontemi', 'odeme', type_='check')
    op.create_check_constraint(
        'odemeyontemi', 'odeme', "yontem IN ('nakit', 'havale_eft', 'diger')"
    )


def downgrade() -> None:
    op.drop_constraint('odemeyontemi', 'odeme', type_='check')
    op.create_check_constraint(
        'odemeyontemi', 'odeme', "yontem IN ('nakit', 'havale_eft', 'pos', 'diger')"
    )
