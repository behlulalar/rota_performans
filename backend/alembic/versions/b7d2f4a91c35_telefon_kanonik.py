"""telefonlari kanonik bicime cevir (+90 ve 10 hane)

Mevcut kullanici.giris (yalnizca "@" icermeyenler), ogrenci.telefon,
iletisim_kisisi.telefon ve antrenor.telefon degerleri satir satir kanonik
bicime ("+90" + 10 hane) cevrilir. Cevrilemeyen degerlere dokunulmaz;
kullanici.giris benzersizligini bozacak cakisma olursa o satir atlanir.

downgrade: no-op. Veri donusumu geri alinamaz (eski yazim bilgisi saklanmaz).

Revision ID: b7d2f4a91c35
Revises: a1c3e5f70912
Create Date: 2026-10-25 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d2f4a91c35'
down_revision: Union[str, None] = 'a1c3e5f70912'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AYIRICILAR = " -()\t"


def _kanonik(metin):
    """app.telefon.normalize ile ayni mantik; gecersizse None."""
    s = "".join(c for c in metin if c not in _AYIRICILAR)
    if s.startswith("+"):
        s = s[1:]
    if not (s.isascii() and s.isdigit()):
        return None
    if len(s) == 12 and s.startswith("90"):
        s = s[2:]
    elif len(s) == 11 and s.startswith("0"):
        s = s[1:]
    if len(s) != 10:
        return None
    return "+90" + s


def _telefon_sutunu(baglanti, tablo: str) -> None:
    satirlar = baglanti.execute(sa.text(f"SELECT id, telefon FROM {tablo} WHERE telefon IS NOT NULL")).fetchall()
    for id_, tel in satirlar:
        yeni = _kanonik(tel)
        if yeni is not None and yeni != tel:
            baglanti.execute(sa.text(f"UPDATE {tablo} SET telefon = :t WHERE id = :i"), {"t": yeni, "i": id_})


def upgrade() -> None:
    baglanti = op.get_bind()

    for tablo in ("ogrenci", "iletisim_kisisi", "antrenor"):
        _telefon_sutunu(baglanti, tablo)

    satirlar = baglanti.execute(sa.text("SELECT id, giris FROM kullanici WHERE giris NOT LIKE '%@%'")).fetchall()
    mevcut = {g for (g,) in baglanti.execute(sa.text("SELECT giris FROM kullanici")).fetchall()}
    for id_, giris in satirlar:
        yeni = _kanonik(giris)
        if yeni is None or yeni == giris or yeni in mevcut:
            continue
        baglanti.execute(sa.text("UPDATE kullanici SET giris = :g WHERE id = :i"), {"g": yeni, "i": id_})
        mevcut.discard(giris)
        mevcut.add(yeni)


def downgrade() -> None:
    # Geri alinamaz veri donusumu: no-op.
    pass
