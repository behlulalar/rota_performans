import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel


class DevamDersi(BaseModel):
    tarih: date
    durum: Literal["geldi", "gelmedi"]
    telafi_mi: bool
    grup_ad: str


class DevamOzeti(BaseModel):
    """Oranlar yüzde (0–100); hiç yoklama yoksa None."""

    katildi: int
    gelmedi: int
    oran: int | None
    son30_katildi: int
    son30_gelmedi: int
    son30_oran: int | None
    ard_arda_gelmedi: int
    son_dersler: list[DevamDersi]  # en yeniden eskiye, en çok 10


class DevamSatiri(BaseModel):
    ogrenci_id: uuid.UUID
    ad: str
    soyad: str
    devam: DevamOzeti


class GrupDevami(BaseModel):
    grup_id: uuid.UUID
    grup_ad: str
    ogrenciler: list[DevamSatiri]
