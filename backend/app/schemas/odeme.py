import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.paket import OdemeYontemi
from app.schemas.paket import GizliTutar


class OdemeAl(BaseModel):
    # Tutar gönderilmez: tam ödeme, sunucu uygulanan fiyatı alır.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    yontem: OdemeYontemi
    tarih: date | None = None
    aciklama: str | None = Field(default=None, max_length=300)


class OdemeIptal(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    neden: str = Field(min_length=3, max_length=200)


class OdemeOgrenci(BaseModel):
    id: uuid.UUID
    ad: str
    soyad: str


class OdemeListeSatiri(BaseModel):
    id: uuid.UUID
    ogrenci_paketi_id: uuid.UUID
    tarih: date
    ogrenci: OdemeOgrenci
    paket_adi: str
    tutar: GizliTutar
    yontem: OdemeYontemi
    aciklama: str | None
    iptal: bool
    iptal_nedeni: str | None
    alan_ad: str | None


class YontemDagilimi(BaseModel):
    yontem: OdemeYontemi
    tutar: GizliTutar
    adet: int


class OdemeOzeti(BaseModel):
    toplam_tutar: GizliTutar
    adet: int
    yontem_dagilimi: list[YontemDagilimi]


class OdemeListe(BaseModel):
    kayitlar: list[OdemeListeSatiri]
    toplam: int
    sayfa: int
    boyut: int
    ozet: OdemeOzeti


class BekleyenPaket(BaseModel):
    ogrenci_paketi_id: uuid.UUID
    ogrenci: OdemeOgrenci
    paket_adi: str
    uygulanan_fiyat: GizliTutar
    atama_tarihi: date
    bekleme_gun: int
