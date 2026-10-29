import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.grup import OgrenciGrupOzet
from app.models.kullanici import Rol
from app.models.ogrenci import Cinsiyet, IletisimRolu, KimlikTur, OgrenciDurum, RizaTuru


class IletisimKisisiGirdi(BaseModel):
    # Yalnızca boşluktan oluşan değerler boş sayılır ve min_length ile reddedilir.
    model_config = ConfigDict(str_strip_whitespace=True)

    # Doluysa mevcut kişi yerinde güncellenir (hesap bağı korunur).
    id: uuid.UUID | None = None
    rol: IletisimRolu
    ad_soyad: str = Field(min_length=1, max_length=200)
    telefon: str = Field(min_length=1, max_length=40)
    birincil: bool


class RizaGirdi(BaseModel):
    aydinlatma: bool
    foto: bool
    whatsapp: bool


class OgrenciOlustur(BaseModel):
    # Yalnızca boşluktan oluşan değerler boş sayılır ve min_length ile reddedilir.
    model_config = ConfigDict(str_strip_whitespace=True)

    ad: str = Field(min_length=1, max_length=100)
    soyad: str = Field(min_length=1, max_length=100)
    anne_adi: str | None = Field(default=None, max_length=100)
    baba_adi: str | None = Field(default=None, max_length=100)
    dogum_tarihi: date
    cinsiyet: Cinsiyet | None = None
    kimlik_tur: KimlikTur
    kimlik_no: str | None = Field(default=None, max_length=40)
    telefon: str | None = Field(default=None, max_length=40)
    iletisim_kisileri: list[IletisimKisisiGirdi]
    rizalar: RizaGirdi


class OgrenciGuncelle(BaseModel):
    # Yalnızca boşluktan oluşan değerler boş sayılır ve min_length ile reddedilir.
    model_config = ConfigDict(str_strip_whitespace=True)

    ad: str | None = Field(default=None, min_length=1, max_length=100)
    soyad: str | None = Field(default=None, min_length=1, max_length=100)
    anne_adi: str | None = Field(default=None, max_length=100)
    baba_adi: str | None = Field(default=None, max_length=100)
    dogum_tarihi: date | None = None
    cinsiyet: Cinsiyet | None = None
    kimlik_tur: KimlikTur | None = None
    kimlik_no: str | None = Field(default=None, max_length=40)
    telefon: str | None = Field(default=None, max_length=40)


class BirincilIletisim(BaseModel):
    ad_soyad: str
    telefon: str
    rol: IletisimRolu


class OgrenciOzet(BaseModel):
    id: uuid.UUID
    ad: str
    soyad: str
    dogum_tarihi: date
    yas: int
    durum: OgrenciDurum
    cinsiyet: Cinsiyet | None
    kimlik_maskeli: str | None
    foto_var: bool
    telefon: str | None
    birincil_iletisim: BirincilIletisim | None


class OgrenciListe(BaseModel):
    kayitlar: list[OgrenciOzet]
    toplam: int
    sayfa: int
    boyut: int


class IletisimKisisiYanit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rol: IletisimRolu
    ad_soyad: str
    telefon: str
    birincil: bool
    whatsapp_izni: bool


class RizaYanit(BaseModel):
    tur: RizaTuru
    verildi: datetime
    geri_cekildi: datetime | None


class HesapBilgi(BaseModel):
    giris: str
    rol: Rol
    aktif: bool
    bagli_ogrenci_sayisi: int


class DersHakki(BaseModel):
    normal: int
    telafi: int


class DersHakkiDetay(DersHakki):
    kullanilabilir_telafi: int


class OgrenciDetay(OgrenciOzet):
    anne_adi: str | None
    baba_adi: str | None
    kimlik_tur: KimlikTur
    kayit_tarihi: date
    iletisim_kisileri: list[IletisimKisisiYanit]
    rizalar: list[RizaYanit]
    uyarilar: list[str]
    gruplar: list[OgrenciGrupOzet] = []
    hesap: HesapBilgi | None = None
    ders_hakki: DersHakkiDetay = DersHakkiDetay(normal=0, telafi=0, kullanilabilir_telafi=0)


class KimlikYanit(BaseModel):
    kimlik_no: str


FotoBoyut = Literal["kucuk", "buyuk"]


class HesapAcGirdi(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    giris: str | None = Field(default=None, max_length=255)


class HesapAcYanit(BaseModel):
    giris: str
    gecici_sifre: str | None
    yeni_hesap: bool


class ResitUyari(BaseModel):
    id: uuid.UUID
    ad: str
    soyad: str
    yas: int
    birincil_rol: IletisimRolu | None
    veli_hesabi_var: bool
    telefon: str | None = None


class ResitGecisiGirdi(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    telefon: str = Field(min_length=1, max_length=40)
    ad_soyad: str | None = Field(default=None, max_length=200)
