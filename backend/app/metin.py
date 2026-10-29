"""Başlık ve isim alanlarının yazımı: "özel ders" -> "Özel Ders", "AHMET YILMAZ" -> "Ahmet Yılmaz"."""
import re
from typing import Annotated

from pydantic import AfterValidator

_AYIRICI = re.compile(r"(\s+|-)")
# Sözcük içinde bağlaç olarak küçük kalanlar (ilk sözcük hariç).
_KUCUK_KALAN = {"ve"}


def tr_buyuk(metin: str) -> str:
    return metin.replace("i", "İ").replace("ı", "I").upper()


def tr_kucuk(metin: str) -> str:
    return metin.replace("İ", "i").replace("I", "ı").lower()


def _kelime(kelime: str, ilk: bool) -> str:
    if not kelime:
        return kelime
    if not ilk and tr_kucuk(kelime) in _KUCUK_KALAN:
        return tr_kucuk(kelime)
    # Rakam içeren kodlar (U10, 8D) olduğu gibi kalır; yalnızca ilk harf büyütülür.
    govde = kelime[1:] if any(c.isdigit() for c in kelime) else tr_kucuk(kelime[1:])
    return tr_buyuk(kelime[0]) + govde


def baslik_yap(metin: str) -> str:
    """Her sözcüğün ilk harfini büyütür, kalanını küçültür; baştaki/sondaki ve arka arkaya boşlukları temizler."""
    parcalar = _AYIRICI.split(metin.strip())
    sonuc: list[str] = []
    ilk = True
    for p in parcalar:
        if p == "-" or p.isspace():
            sonuc.append(" " if p.isspace() else p)
            continue
        sonuc.append(_kelime(p, ilk))
        ilk = False
    return "".join(sonuc)


Baslik = Annotated[str, AfterValidator(baslik_yap)]
