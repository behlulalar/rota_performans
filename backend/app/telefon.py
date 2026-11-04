_AYIRICILAR = " -()\t"
_HATA = "Telefon numarası geçersiz: ülke kodu ardından numara girin (Türkiye için +90 ardından 10 haneden oluşmalı)"


def sade(metin: str) -> str:
    """Boşluk, tire ve parantezleri atar."""
    return "".join(c for c in metin if c not in _AYIRICILAR)


def normalize(metin: str) -> str:
    """Kanonik biçimi ("+" + ülke kodu + numara) döndürür; geçersizse ValueError.

    "+" ile başlayan numara uluslararası kabul edilir: Türkiye (+90) için tam 10 hane, diğer ülkeler için
    ülke kodu dahil 8–15 hane (E.164). "+" yoksa Türkiye biçimleri (5XX…, 05XX…, 905XX…) geçerlidir.
    """
    s = sade(metin)
    uluslararasi = s.startswith("+")
    if uluslararasi:
        s = s[1:]
    if not (s.isascii() and s.isdigit()):
        raise ValueError(_HATA)
    if uluslararasi:
        if s.startswith("0"):
            raise ValueError(_HATA)
        gecerli = len(s) == 12 if s.startswith("90") else 8 <= len(s) <= 15
        if not gecerli:
            raise ValueError(_HATA)
        return "+" + s
    if len(s) == 12 and s.startswith("90"):
        s = s[2:]
    elif len(s) == 11 and s.startswith("0"):
        s = s[1:]
    if len(s) != 10:
        raise ValueError(_HATA)
    return "+90" + s


def giris_icin(metin: str) -> str | None:
    """Çözümleme başarılıysa kanonik telefonu, değilse None döndürür."""
    try:
        return normalize(metin)
    except ValueError:
        return None
