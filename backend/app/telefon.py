_AYIRICILAR = " -()\t"
_HATA = "Telefon numarası +90 ardından 10 haneden oluşmalı"


def sade(metin: str) -> str:
    """Boşluk, tire ve parantezleri atar."""
    return "".join(c for c in metin if c not in _AYIRICILAR)


def normalize(metin: str) -> str:
    """Kanonik biçimi ("+90" + 10 hane) döndürür; geçersizse ValueError."""
    s = sade(metin)
    if s.startswith("+"):
        s = s[1:]
    if not (s.isascii() and s.isdigit()):
        raise ValueError(_HATA)
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
