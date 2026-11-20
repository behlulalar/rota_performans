"""devamsizlik sebebi ve aylik telafi suresi

Yoklamaya `sebep` (izinli, raporlu, yarisma, devamsiz) ve `aciklama`; deftere `telafi_suresi_doldu` hareket türü.
Var olan devamsızlık telafi haklarına (telafi +1) `son_kullanma` yazılır: dersin ayının son günü, ancak en erken
geçişin yapıldığı ayın son günü (var olan haklar geriye dönük yanmaz).

Revision ID: fcbb49787e58
Revises: c7a1e3f95b26
Create Date: 2026-11-20 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'fcbb49787e58'
down_revision: Union[str, None] = 'c7a1e3f95b26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ESKI_TURLER = "'paket_yuklemesi', 'ders_kullanimi', 'devamsizlik', 'telafi_kullanimi', 'manuel_duzeltme', 'iptal'"
YENI_TURLER = ESKI_TURLER + ", 'telafi_suresi_doldu'"

# Var olan devamsızlık telafi hakları: geri alınmış olsalar da (bakiye etkisi zaten sıfırdır) tutarlılık için doldurulur.
# Geçişte var olan haklar geriye dönük yanmaz: son gün, dersin ayının sonu ile geçişin yapıldığı ayın sonundan
# (İstanbul) hangisi geçse odur.
DOLDUR_SQL = """
UPDATE ders_hakki_hareketi h
SET son_kullanma = GREATEST(
    (date_trunc('month', o.tarih) + interval '1 month - 1 day')::date,
    (date_trunc('month', (now() AT TIME ZONE 'Europe/Istanbul')::date) + interval '1 month - 1 day')::date
)
FROM yoklama y JOIN ders_oturumu o ON o.id = y.oturum_id
WHERE h.yoklama_id = y.id AND h.tur = 'devamsizlik' AND h.sayac = 'telafi' AND h.miktar > 0
  AND h.son_kullanma IS NULL
"""


def _tetikleyicisiz(sql: str) -> None:
    # Defter tetikleyicisi UPDATE'i yasaklar. Tek seferlik veri düzeltmesi için aynı işlem içinde
    # geçici olarak kapatılır ve hemen açılır (bkz. 088395710169_yoklama_surumu).
    op.execute("ALTER TABLE ders_hakki_hareketi DISABLE TRIGGER ders_hakki_hareketi_degistirilemez")
    op.execute(sql)
    op.execute("ALTER TABLE ders_hakki_hareketi ENABLE TRIGGER ders_hakki_hareketi_degistirilemez")


def upgrade() -> None:
    op.add_column('yoklama', sa.Column('sebep', sa.String(length=24), nullable=True))
    op.add_column('yoklama', sa.Column('aciklama', sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f('ck_yoklama_devamsizliksebebi'), 'yoklama', "sebep IN ('izinli', 'raporlu', 'yarisma', 'devamsiz')"
    )
    op.create_check_constraint(op.f('ck_yoklama_sebep_yalniz_gelmedi'), 'yoklama', "sebep IS NULL OR durum = 'gelmedi'")
    op.create_check_constraint(
        op.f('ck_yoklama_aciklama_uzunlugu'), 'yoklama', 'aciklama IS NULL OR length(aciklama) <= 500'
    )

    op.drop_constraint(op.f('ck_ders_hakki_hareketi_hareketturu'), 'ders_hakki_hareketi', type_='check')
    op.create_check_constraint(op.f('ck_ders_hakki_hareketi_hareketturu'), 'ders_hakki_hareketi', f"tur IN ({YENI_TURLER})")

    _tetikleyicisiz(DOLDUR_SQL)


def downgrade() -> None:
    baglanti = op.get_bind()
    sayi = baglanti.execute(sa.text("SELECT count(*) FROM ders_hakki_hareketi WHERE tur = 'telafi_suresi_doldu'")).scalar()
    if sayi:
        # Defter satırı silinmez: süresi dolan telafi kayıtları varken geri dönüş bakiyeyi bozar.
        raise RuntimeError(f"{sayi} adet telafi_suresi_doldu hareketi var, geri dönüş yapılamaz")
    _tetikleyicisiz(
        "UPDATE ders_hakki_hareketi SET son_kullanma = NULL WHERE tur = 'devamsizlik' AND son_kullanma IS NOT NULL"
    )
    op.drop_constraint(op.f('ck_ders_hakki_hareketi_hareketturu'), 'ders_hakki_hareketi', type_='check')
    op.create_check_constraint(op.f('ck_ders_hakki_hareketi_hareketturu'), 'ders_hakki_hareketi', f"tur IN ({ESKI_TURLER})")

    op.drop_constraint(op.f('ck_yoklama_aciklama_uzunlugu'), 'yoklama', type_='check')
    op.drop_constraint(op.f('ck_yoklama_sebep_yalniz_gelmedi'), 'yoklama', type_='check')
    op.drop_constraint(op.f('ck_yoklama_devamsizliksebebi'), 'yoklama', type_='check')
    op.drop_column('yoklama', 'aciklama')
    op.drop_column('yoklama', 'sebep')
