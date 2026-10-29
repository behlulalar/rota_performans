from datetime import datetime

from pydantic import BaseModel

from app.models.bildirim import BildirimDurum, BildirimKanal


class DurumSayilari(BaseModel):
    bekliyor: int = 0
    gonderildi: int = 0
    hata: int = 0
    iptal: int = 0


class BildirimOzeti(BaseModel):
    son_7_gun: DurumSayilari
    bugun: DurumSayilari
    push_etkin: bool
    push_cihaz_sayisi: int
    push_kullanici_sayisi: int
    geciken_bekleyen: int


class BildirimOgrenci(BaseModel):
    id: str
    ad: str
    soyad: str


class BildirimAlici(BaseModel):
    ad_soyad: str
    rol: str


class BildirimSatiri(BaseModel):
    id: int
    olusturma: datetime
    planli_zaman: datetime
    gonderim_zamani: datetime | None
    kanal: BildirimKanal
    sablon: str
    sablon_etiket: str
    durum: BildirimDurum
    deneme: int
    hata: str | None
    ogrenci: BildirimOgrenci
    alici: BildirimAlici
    metin: str


class BildirimListesi(BaseModel):
    kayitlar: list[BildirimSatiri]
    toplam: int
    sayfa: int
    boyut: int


class BildirimIslemi(BaseModel):
    id: int
    durum: BildirimDurum
