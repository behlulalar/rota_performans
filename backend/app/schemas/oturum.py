import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, model_validator

from app.models.program import OturumDurum
from app.models.yoklama import HareketTuru, Sayac, YoklamaDurum
from app.schemas.ogrenci import DersHakki

EN_COK_GUN = 62


class UretGirdi(BaseModel):
    baslangic: date
    bitis: date

    @model_validator(mode="after")
    def _aralik(self):
        if self.bitis < self.baslangic:
            raise ValueError("Bitiş tarihi başlangıçtan önce olamaz")
        if (self.bitis - self.baslangic).days + 1 > EN_COK_GUN:
            raise ValueError(f"Aralık en çok {EN_COK_GUN} gün olabilir")
        return self


class UretYanit(BaseModel):
    olusturulan: int


class OturumGrup(BaseModel):
    id: uuid.UUID
    ad: str


class OturumAntrenor(BaseModel):
    id: uuid.UUID
    ad_soyad: str


class OturumOzet(BaseModel):
    id: uuid.UUID
    tarih: date
    baslangic: time
    bitis: time
    durum: OturumDurum
    grup: OturumGrup
    antrenor: OturumAntrenor | None
    ogrenci_sayisi: int
    yoklama_alindi: bool


class OturumOgrenci(BaseModel):
    ogrenci_id: uuid.UUID
    ad: str
    soyad: str
    foto_var: bool
    telafi_mi: bool
    yoklama: YoklamaDurum | None
    bakiye: DersHakki


class OturumDetay(OturumOzet):
    ogrenciler: list[OturumOgrenci]


class YoklamaGirdi(BaseModel):
    ogrenci_id: uuid.UUID
    durum: YoklamaDurum


class HareketOturum(BaseModel):
    tarih: date
    grup_ad: str


class HareketYanit(BaseModel):
    id: int
    zaman: datetime
    sayac: Sayac
    miktar: int
    tur: HareketTuru
    neden: str | None
    oturum: HareketOturum | None


class DersHakkiYanit(DersHakki):
    hareketler: list[HareketYanit]

