from pydantic import BaseModel, ConfigDict, Field


class AyarYaniti(BaseModel):
    ad: str
    telefon: str | None
    eposta: str | None
    adres: str | None
    instagram: str | None
    geri_alma_dakika: int
    azaldi_esigi: int
    wa_saatlik_limit: int
    wa_gunluk_limit: int
    wa_baslangic_saat: int
    wa_bitis_saat: int
    wa_push_varsa_atla: bool


class KulupIletisim(BaseModel):
    """Velilerin "Bize ulaşın" sayfası: ayarların yalnız iletişim kısmı."""

    ad: str
    telefon: str | None
    eposta: str | None
    adres: str | None
    instagram: str | None


class KulupTanitim(BaseModel):
    """Giriş sayfası (oturumsuz): yalnız kulüp adı ve Instagram."""

    ad: str
    instagram: str | None


class AyarGuncelle(BaseModel):
    """Kısmi güncelleme: gönderilmeyen alan değişmez. Boş telefon/e-posta/adres/instagram değeri siler."""

    model_config = ConfigDict(extra="forbid")

    ad: str | None = Field(default=None, max_length=120)
    telefon: str | None = Field(default=None, max_length=40)
    eposta: str | None = Field(default=None, max_length=254)
    adres: str | None = Field(default=None, max_length=500)
    instagram: str | None = Field(default=None, max_length=200)
    geri_alma_dakika: int | None = Field(default=None, ge=1, le=15)
    azaldi_esigi: int | None = Field(default=None, ge=1, le=5)
    wa_saatlik_limit: int | None = Field(default=None, ge=1, le=200)
    wa_gunluk_limit: int | None = Field(default=None, ge=1, le=1000)
    wa_baslangic_saat: int | None = Field(default=None, ge=0, le=23)
    wa_bitis_saat: int | None = Field(default=None, ge=1, le=24)
    wa_push_varsa_atla: bool | None = None
