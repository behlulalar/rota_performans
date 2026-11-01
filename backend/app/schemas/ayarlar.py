from pydantic import BaseModel, ConfigDict, Field


class AyarYaniti(BaseModel):
    ad: str
    telefon: str | None
    eposta: str | None
    adres: str | None
    geri_alma_dakika: int
    azaldi_esigi: int


class KulupIletisim(BaseModel):
    """Velilerin "Bize ulaşın" sayfası: ayarların yalnız iletişim kısmı."""

    ad: str
    telefon: str | None
    eposta: str | None
    adres: str | None


class AyarGuncelle(BaseModel):
    """Kısmi güncelleme: gönderilmeyen alan değişmez. Boş telefon/e-posta/adres değeri siler."""

    model_config = ConfigDict(extra="forbid")

    ad: str | None = Field(default=None, max_length=120)
    telefon: str | None = Field(default=None, max_length=40)
    eposta: str | None = Field(default=None, max_length=254)
    adres: str | None = Field(default=None, max_length=500)
    geri_alma_dakika: int | None = Field(default=None, ge=1, le=15)
    azaldi_esigi: int | None = Field(default=None, ge=1, le=5)
