import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.metin import Baslik


class YoneticiOlustur(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    ad_soyad: Baslik = Field(min_length=1, max_length=200)
    # E-posta veya telefon.
    giris: str = Field(min_length=1, max_length=255)
    # İsteğe bağlı ikinci giriş yolu (telefon).
    telefon: str | None = Field(default=None, max_length=32)


class YoneticiGuncelle(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    ad_soyad: Baslik | None = Field(default=None, min_length=1, max_length=200)
    giris: str | None = Field(default=None, min_length=1, max_length=255)
    aktif: bool | None = None
    # Boş/None: telefonu kaldırır.
    telefon: str | None = Field(default=None, max_length=32)


class YoneticiOzet(BaseModel):
    id: uuid.UUID
    ad_soyad: str | None
    giris: str
    telefon: str | None = None
    aktif: bool
    son_giris: datetime | None
    olusturma: datetime
    # Listeyi isteyen yöneticinin kendi satırı.
    ben: bool
    # Teknik destek hesabı: listede salt okunur görünür (yönetici düzenleyemez), son yönetici sayımına girmez.
    destek: bool = False


class YoneticiOlusturYanit(BaseModel):
    yonetici: YoneticiOzet
    gecici_sifre: str
