import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.models.paket import OdemeYontemi, OgrenciPaketiDurum, PaketTuru

# Tutarlar JSON'da her zaman "3400.00" biçiminde metin olarak çıkar (float yok).
Tutar = Annotated[Decimal, PlainSerializer(lambda d: f"{d:.2f}", return_type=str, when_used="json")]


class PaketOlustur(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ad: str = Field(min_length=1, max_length=100)
    tur: PaketTuru
    ders_sayisi: int = Field(gt=0, le=1000)
    sure_ay: int = Field(gt=0, le=120)
    varsayilan_fiyat: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class PaketGuncelle(BaseModel):
    # ders_sayisi / sure_ay / tur gönderilirse extra=forbid ile 422 döner: geçmiş kayıtlar bozulmaz.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ad: str | None = Field(default=None, min_length=1, max_length=100)
    varsayilan_fiyat: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    aktif: bool | None = None


class PaketYanit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ad: str
    tur: PaketTuru
    ders_sayisi: int
    sure_ay: int
    varsayilan_fiyat: Tutar
    aktif: bool
    olusturma: datetime


class PaketAta(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    paket_id: uuid.UUID
    baslangic: date | None = None
    ozel_fiyat: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    ozel_fiyat_nedeni: str | None = Field(default=None, max_length=200)


class OdemeSatiri(BaseModel):
    id: uuid.UUID
    tutar: Tutar
    tarih: date
    yontem: OdemeYontemi
    aciklama: str | None
    iptal: bool
    iptal_nedeni: str | None = None
    alan_ad: str | None = None


class OgrenciPaketiYanit(BaseModel):
    id: uuid.UUID
    ogrenci_id: uuid.UUID
    paket_id: uuid.UUID
    paket_adi: str
    ders_sayisi: int
    liste_fiyati: Tutar
    uygulanan_fiyat: Tutar
    fiyat_ozel_mi: bool
    durum: OgrenciPaketiDurum
    baslangic: date | None
    bitis: date | None
    toplam_odenen: Tutar
    olusturma: datetime
    odemeler: list[OdemeSatiri] = []
