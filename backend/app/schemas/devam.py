import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.yoklama import DevamsizlikSebebi


class DevamDersi(BaseModel):
    tarih: date
    durum: Literal["geldi", "gelmedi"]
    sebep: DevamsizlikSebebi | None = None  # yalnız gelmedi; eski kayıtlarda boş
    aciklama: str | None = None  # İÇ not: yalnız yönetim/antrenör uçları; veli şemalarına asla konmaz
    telafi_mi: bool
    ek_ders_mi: bool = False  # devam oranına girmez; yalnız son derslerde görünür
    grup_ad: str


class GelmediSebepleri(BaseModel):
    """`gelmedi` sayısının sebebe göre dağılımı (toplamı `gelmedi`ye eşittir). `bilinmiyor`: sebepsiz eski kayıtlar."""

    izinli: int = 0
    raporlu: int = 0
    yarisma: int = 0
    devamsiz: int = 0
    bilinmiyor: int = 0


class DevamOzeti(BaseModel):
    """Oranlar yüzde (0–100); hiç yoklama yoksa None. Oran sebepten bağımsızdır: her gelmedi oranı düşürür."""

    katildi: int
    gelmedi: int
    gelmedi_sebepleri: GelmediSebepleri
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
    telafi_bakiyesi: int = 0  # defterdeki telafi sayacı (ders_hakki.bakiyeler); eksiye düşmez


class GrupDevami(BaseModel):
    grup_id: uuid.UUID
    grup_ad: str
    ogrenciler: list[DevamSatiri]
