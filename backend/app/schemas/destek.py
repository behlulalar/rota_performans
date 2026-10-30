import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.bildirim import BildirimDurum, BildirimKanal
from app.models.kullanici import Rol


class Ping(BaseModel):
    ok: bool
    gecikme_ms: float | None = None


class IsciDurumu(BaseModel):
    canli: bool
    son_atis: datetime | None = None
    saniye_once: int | None = None


class KuyrukSayilari(BaseModel):
    bekliyor: int = 0
    gonderildi: int = 0
    hata: int = 0
    iptal: int = 0
    geciken_bekleyen: int = 0


class SistemDurumu(BaseModel):
    ortam: str
    surum: str
    veritabani: Ping
    redis: Ping
    isci: IsciDurumu
    bildirim_kuyrugu: KuyrukSayilari
    push_yapilandirildi: bool
    whatsapp_yapilandirildi: bool


class HesapSatiri(BaseModel):
    id: uuid.UUID
    giris: str
    ad_soyad: str | None
    rol: Rol
    aktif: bool
    kilitli: bool
    kilit_bitis: datetime | None
    son_giris: datetime | None
    olusturma: datetime
    sifre_degistirmeli: bool
    # Yalnız destek rolü için anlamlı (diğerlerinde False).
    totp_aktif: bool
    ben: bool


class HesapListesi(BaseModel):
    kayitlar: list[HesapSatiri]
    toplam: int
    sayfa: int
    boyut: int


class OturumSatiri(BaseModel):
    id: uuid.UUID
    olusturma: datetime
    bitis: datetime
    hatirla: bool
    # İptal edilmemiş ve süresi dolmamış.
    aktif: bool


class OturumKapatYaniti(BaseModel):
    kapatilan: int


class DestekBildirimSatiri(BaseModel):
    id: int
    olusturma: datetime
    planli_zaman: datetime
    gonderim_zamani: datetime | None
    kanal: BildirimKanal
    sablon: str
    durum: BildirimDurum
    deneme: int
    hata: str | None
    # Ham içerik: şablon parametreleri ve ilişkili kayıt kimlikleri.
    parametreler: dict | None
    ogrenci_id: uuid.UUID
    alici_iletisim_id: uuid.UUID
    yoklama_id: uuid.UUID | None
    duyuru_id: uuid.UUID | None
    metin: str


class DestekBildirimListesi(BaseModel):
    kayitlar: list[DestekBildirimSatiri]
    toplam: int
    sayfa: int
    boyut: int


class TopluIslemIstegi(BaseModel):
    # Ya açık id listesi ya da tum_hatalilar=true (ikisi birden olamaz).
    ids: list[int] | None = Field(default=None, max_length=500)
    tum_hatalilar: bool = False

    @model_validator(mode="after")
    def _biri_secili(self):
        if self.tum_hatalilar == bool(self.ids):
            raise ValueError("ids listesi ya da tum_hatalilar=true verilmeli (ikisi birden değil)")
        return self


class TopluIslemYaniti(BaseModel):
    islenen: int
    # Bulunamayan ya da durumu uygun olmayan (ör. gönderilmiş) kayıtlar.
    atlanan: int
