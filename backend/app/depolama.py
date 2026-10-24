"""Dosya depolama soyutlaması. Şimdilik yerel disk; ileride nesne depolamaya geçilebilir.

Anahtar yalnızca 32 haneli küçük harfli hex olabilir (yol geçişi engellenir). Her anahtarın
birden çok boyutu olur (ör. kucuk, buyuk).
"""
import re
from pathlib import Path
from typing import Protocol

from app.config import settings

_ANAHTAR = re.compile(r"^[0-9a-f]{32}$")
_BOYUTLAR = ("kucuk", "buyuk")


class DepolamaHatasi(ValueError):
    pass


class Depolama(Protocol):
    def kaydet(self, anahtar: str, boyut: str, veri: bytes) -> None: ...
    def oku(self, anahtar: str, boyut: str) -> bytes | None: ...
    def sil(self, anahtar: str) -> None: ...


class DiskDepolama:
    def __init__(self, kok: str | None = None):
        self._kok = kok

    def _dizin(self) -> Path:
        return Path(self._kok or settings.dosya_dizini)

    def _yol(self, anahtar: str, boyut: str) -> Path:
        if not _ANAHTAR.fullmatch(anahtar) or boyut not in _BOYUTLAR:
            raise DepolamaHatasi("Geçersiz dosya anahtarı")
        return self._dizin() / f"{anahtar}_{boyut}.jpg"

    def kaydet(self, anahtar: str, boyut: str, veri: bytes) -> None:
        yol = self._yol(anahtar, boyut)
        yol.parent.mkdir(parents=True, exist_ok=True)
        gecici = yol.with_suffix(".tmp")
        gecici.write_bytes(veri)
        gecici.replace(yol)

    def oku(self, anahtar: str, boyut: str) -> bytes | None:
        yol = self._yol(anahtar, boyut)
        try:
            return yol.read_bytes()
        except FileNotFoundError:
            return None

    def sil(self, anahtar: str) -> None:
        for boyut in _BOYUTLAR:
            self._yol(anahtar, boyut).unlink(missing_ok=True)


depolama: Depolama = DiskDepolama()
