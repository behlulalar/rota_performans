import re

_TELEFON = re.compile(r"^\+?\d{7,15}$")
_AYIRICILAR = " -()\t"


def sade(metin: str) -> str:
    """Boşluk, tire ve parantezleri atar."""
    return "".join(c for c in metin if c not in _AYIRICILAR)


def normalize(telefon: str) -> str:
    """Sadeleştirilmiş telefonu döndürür; geçersizse ValueError."""
    s = sade(telefon)
    if not _TELEFON.fullmatch(s):
        raise ValueError("Geçersiz telefon numarası")
    return s
