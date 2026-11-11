import uuid

from pydantic import BaseModel, ConfigDict, Field
from app.metin import Baslik


class AntrenorOlustur(BaseModel):
    # Yalnızca boşluktan oluşan değerler boş sayılır ve min_length ile reddedilir.
    model_config = ConfigDict(str_strip_whitespace=True)

    ad_soyad: Baslik = Field(min_length=1, max_length=200)
    # Giriş bilgisi de bu telefondur (yalnız telefonla giriş).
    telefon: str = Field(min_length=1, max_length=40)
    grup_idleri: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class AntrenorGuncelle(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    ad_soyad: Baslik | None = Field(default=None, min_length=1, max_length=200)
    telefon: str | None = Field(default=None, max_length=40)
    aktif: bool | None = None
    # None/yok: gruplara dokunulmaz; liste: antrenörün aktif grupları tam olarak bunlar olur.
    grup_idleri: list[uuid.UUID] | None = Field(default=None, max_length=200)


class AntrenorOzet(BaseModel):
    id: uuid.UUID
    ad_soyad: str
    telefon: str | None
    aktif: bool
    giris: str | None
    grup_sayisi: int
    grup_idleri: list[uuid.UUID] = Field(default_factory=list)


class AntrenorOlusturYanit(BaseModel):
    antrenor: AntrenorOzet
    gecici_sifre: str


class SifreSifirlaYanit(BaseModel):
    gecici_sifre: str
