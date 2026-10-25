from datetime import date

from pydantic import BaseModel

from app.models.paket import OdemeYontemi
from app.schemas.paket import Tutar


class RaporDonem(BaseModel):
    yil: int
    ay: int
    baslangic: date
    bitis: date


class GelirOzeti(BaseModel):
    toplam_tahsilat: Tutar
    odeme_adedi: int
    ortalama_odeme: Tutar
    onceki_ay_tahsilat: Tutar
    degisim_yuzde: float | None
    iptal_edilen_tutar: Tutar
    iptal_adedi: int
    indirim_toplami: Tutar
    ucretsiz_paket_adedi: int


class GelirBekleyen(BaseModel):
    adet: int
    tutar: Tutar
    gecikmis_adet: int
    gecikmis_tutar: Tutar


class GelirYontem(BaseModel):
    yontem: OdemeYontemi
    tutar: Tutar
    adet: int
    yuzde: float


class GelirPaket(BaseModel):
    paket_adi: str
    tutar: Tutar
    adet: int


class GelirGun(BaseModel):
    tarih: date
    tutar: Tutar
    adet: int


class GelirAy(BaseModel):
    yil: int
    ay: int
    tutar: Tutar
    adet: int


class GelirRaporu(BaseModel):
    donem: RaporDonem
    ozet: GelirOzeti
    bekleyen: GelirBekleyen
    yontem_dagilimi: list[GelirYontem]
    paket_dagilimi: list[GelirPaket]
    gunluk: list[GelirGun]
    aylik_seri: list[GelirAy]
