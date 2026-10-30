import uuid
from datetime import date, time

from pydantic import BaseModel

from app.schemas.paket import GizliTutar


class OgrenciSayilari(BaseModel):
    aktif: int
    pasif: int
    bu_ay_kayit: int


class ProgramSlotu(BaseModel):
    gun: int
    baslangic: time
    bitis: time


class GrupDolulugu(BaseModel):
    id: uuid.UUID
    ad: str
    ogrenci_sayisi: int
    kontenjan: int
    program: list[ProgramSlotu] = []


class GrupOzeti(BaseModel):
    aktif_grup: int
    toplam_kontenjan: int
    dolu: int
    doluluk_listesi: list[GrupDolulugu]


class AntrenorSayisi(BaseModel):
    aktif: int


class BekleyenOdeme(BaseModel):
    adet: int
    toplam_tutar: GizliTutar


class SonKayit(BaseModel):
    id: uuid.UUID
    ad: str
    soyad: str
    kayit_tarihi: date
    foto_var: bool


class GenelBakisYanit(BaseModel):
    ogrenci: OgrenciSayilari
    hesapsiz_aktif_ogrenci: int
    grupsuz_aktif_ogrenci: int
    gruplar: GrupOzeti
    antrenor: AntrenorSayisi
    bekleyen_odeme: BekleyenOdeme
    son_kayitlar: list[SonKayit]
