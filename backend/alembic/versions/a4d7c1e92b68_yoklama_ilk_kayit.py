"""yoklama ilk kayit zamani (antrenor icin 1 saatlik kilit)

ders_oturumu.yoklama_ilk_kayit: yoklamanin ilk kaydedildigi an. Var olan oturumlar icin en erken yoklama
zamani yazilir (yoklama.zaman duzeltmelerde guncellendiginden bu, ilk kayda bir ust sinirdir).

Revision ID: a4d7c1e92b68
Revises: fcbb49787e58
Create Date: 2026-11-20 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a4d7c1e92b68'
down_revision: Union[str, None] = 'fcbb49787e58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ders_oturumu', sa.Column('yoklama_ilk_kayit', sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE ders_oturumu o SET yoklama_ilk_kayit = y.ilk
        FROM (SELECT oturum_id, min(zaman) AS ilk FROM yoklama GROUP BY oturum_id) y
        WHERE y.oturum_id = o.id
        """
    )


def downgrade() -> None:
    op.drop_column('ders_oturumu', 'yoklama_ilk_kayit')
