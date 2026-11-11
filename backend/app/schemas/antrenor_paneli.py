import uuid
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.metin import Baslik
from app.models.program import OturumDurum
from app.schemas.oturum import OturumGrup

# "iptal": iptal edilmiş derste yoklama beklenmez.
YoklamaDurumu = Literal["bekliyor", "alindi", "eksik", "iptal"]


class BugunDers(BaseModel):
    id: uuid.UUID
    tarih: date
    grup: OturumGrup
    baslangic: time
    bitis: time
    durum: OturumDurum
    beklenen_ogrenci: int
    yoklama_alinan: int
    yoklama_durumu: YoklamaDurumu
    yoklama_acik: bool
    telafi_sayisi: int


class BugunOzet(BaseModel):
    ders_sayisi: int
    toplam_ogrenci: int
    # Bugünün bitmiş dersleri arasında yoklaması tamamlanmamış olanlar.
    yoklama_bekleyen: int


class BugunYanit(BaseModel):
    tarih: date
    dersler: list[BugunDers]
    siradaki: uuid.UUID | None
    ozet: BugunOzet
    # Son 7 günde (bugün dahil) bitmiş ama yoklaması tamamlanmamış dersler, eskiden yeniye.
    eksik_yoklamalar: list[BugunDers]


class AntrenorProfil(BaseModel):
    ad_soyad: str
    telefon: str | None
    giris: str


class AntrenorProfilGuncelle(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ad_soyad: Baslik | None = Field(default=None, min_length=1, max_length=200)
