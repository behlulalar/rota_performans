from datetime import date
from typing import Annotated

from pydantic import BaseModel

from app.maskele import GIZLI_TUTAR
from app.models.paket import OdemeYontemi
from app.schemas.paket import GizliTutar


class RaporDonem(BaseModel):
    yil: int
    ay: int
    baslangic: date
    bitis: date


class GelirOzeti(BaseModel):
    toplam_tahsilat: GizliTutar
    odeme_adedi: int
    ortalama_odeme: GizliTutar
    onceki_ay_tahsilat: GizliTutar
    degisim_yuzde: Annotated[float | None, GIZLI_TUTAR]
    iptal_edilen_tutar: GizliTutar
    iptal_adedi: int
    indirim_toplami: GizliTutar
    ucretsiz_paket_adedi: int


class GelirBekleyen(BaseModel):
    adet: int
    tutar: GizliTutar
    gecikmis_adet: int
    gecikmis_tutar: GizliTutar


class GelirYontem(BaseModel):
    yontem: OdemeYontemi
    tutar: GizliTutar
    adet: int
    yuzde: float


class GelirPaket(BaseModel):
    paket_adi: str
    tutar: GizliTutar
    adet: int


class GelirGun(BaseModel):
    tarih: date
    tutar: GizliTutar
    adet: int


class GelirAy(BaseModel):
    yil: int
    ay: int
    tutar: GizliTutar
    adet: int


class GelirRaporu(BaseModel):
    donem: RaporDonem
    ozet: GelirOzeti
    bekleyen: GelirBekleyen
    yontem_dagilimi: list[GelirYontem]
    paket_dagilimi: list[GelirPaket]
    gunluk: list[GelirGun]
    aylik_seri: list[GelirAy]
