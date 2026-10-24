import re
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SAAT = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ProgramSlot(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: uuid.UUID | None = None
    gun: int = Field(ge=1, le=7)  # 1 = pazartesi ... 7 = pazar
    baslangic: str
    bitis: str

    @field_validator("baslangic", "bitis")
    @classmethod
    def _saat(cls, deger: str) -> str:
        if not _SAAT.fullmatch(deger):
            raise ValueError("Saat HH:MM biçiminde olmalı")
        return deger

    @model_validator(mode="after")
    def _sira(self):
        # HH:MM sıfır dolgulu olduğundan karakter dizisi karşılaştırması saat sırasıyla aynıdır.
        if self.bitis <= self.baslangic:
            raise ValueError("Bitiş saati başlangıçtan sonra olmalı")
        return self


class GrupOlustur(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    ad: str = Field(min_length=1, max_length=100)
    antrenor_id: uuid.UUID | None = None
    kontenjan: int = Field(ge=1, le=1000)
    program: list[ProgramSlot] = []


class GrupGuncelle(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    ad: str | None = Field(default=None, min_length=1, max_length=100)
    antrenor_id: uuid.UUID | None = None
    kontenjan: int | None = Field(default=None, ge=1, le=1000)
    aktif: bool | None = None


class OgrenciEkle(BaseModel):
    ogrenci_id: uuid.UUID


class GrupAntrenor(BaseModel):
    id: uuid.UUID
    ad_soyad: str


class GrupOzet(BaseModel):
    id: uuid.UUID
    ad: str
    antrenor: GrupAntrenor | None
    kontenjan: int
    aktif: bool
    ogrenci_sayisi: int
    program: list[ProgramSlot]


class GrupOgrenci(BaseModel):
    id: uuid.UUID
    ad: str
    soyad: str
    yas: int
    foto_var: bool
    katilim_baslangic: date


class GrupDetay(GrupOzet):
    ogrenciler: list[GrupOgrenci]


class OgrenciGrupOzet(BaseModel):
    id: uuid.UUID
    ad: str
