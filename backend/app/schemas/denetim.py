import uuid
from datetime import datetime

from pydantic import BaseModel


class DenetimKullanici(BaseModel):
    id: uuid.UUID
    giris: str
    ad_soyad: str | None = None
    rol: str


class DenetimSatiri(BaseModel):
    id: int
    zaman: datetime
    kullanici: DenetimKullanici | None = None
    islem: str
    hedef_tur: str | None = None
    hedef_id: str | None = None
    ip: str | None = None
    detay: dict | None = None


class DenetimListe(BaseModel):
    items: list[DenetimSatiri]
    toplam: int
    sayfa: int
    boyut: int
