import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from app.metin import Baslik

from app.maskele import GIZLI_TUTAR
from app.models.paket import OdemeYontemi, OgrenciPaketiDurum, PaketTuru

# Tutarlar JSON'da her zaman "3400.00" biçiminde metin olarak çıkar (float yok).
Tutar = Annotated[Decimal, PlainSerializer(lambda d: f"{d:.2f}", return_type=str, when_used="json")]
# Yönetici ekranlarındaki tutar: teknik destek isteğinde app.maskele.tutar_gizle ile null olur.
GizliTutar = Annotated[
    Decimal | None,
    PlainSerializer(lambda d: None if d is None else f"{d:.2f}", return_type=str | None, when_used="json"),
    GIZLI_TUTAR,
]


class PaketOlustur(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ad: Baslik = Field(min_length=1, max_length=100)
    tur: PaketTuru
    ders_sayisi: int = Field(gt=0, le=1000)
    sure_ay: int = Field(gt=0, le=120)
    varsayilan_fiyat: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    aciklama: str | None = Field(default=None, max_length=1000)


class PaketGuncelle(BaseModel):
    # Atanmış paketlere ders sayısı ve fiyat kopyalanır (OgrenciPaketi); bu yüzden tanım değişikliği yalnız yeni atamaları etkiler.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ad: Baslik | None = Field(default=None, min_length=1, max_length=100)
    tur: PaketTuru | None = None
    ders_sayisi: int | None = Field(default=None, gt=0, le=1000)
    sure_ay: int | None = Field(default=None, gt=0, le=120)
    varsayilan_fiyat: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    aciklama: str | None = Field(default=None, max_length=1000)
    aktif: bool | None = None


class PaketYanit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ad: str
    tur: PaketTuru
    ders_sayisi: int
    sure_ay: int
    varsayilan_fiyat: GizliTutar
    aciklama: str | None
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
    tutar: GizliTutar
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
    liste_fiyati: GizliTutar
    uygulanan_fiyat: GizliTutar
    fiyat_ozel_mi: bool
    durum: OgrenciPaketiDurum
    baslangic: date | None
    bitis: date | None
    toplam_odenen: GizliTutar
    olusturma: datetime
    odemeler: list[OdemeSatiri] = []
