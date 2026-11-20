import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.program import OturumDurum
from app.models.yoklama import ACIKLAMA_EN_COK, DevamsizlikSebebi, HareketTuru, Sayac, YoklamaDurum
from app.schemas.ogrenci import DersHakki

EN_COK_GUN = 62


class UretGirdi(BaseModel):
    baslangic: date
    bitis: date

    @model_validator(mode="after")
    def _aralik(self):
        if self.bitis < self.baslangic:
            raise ValueError("Bitiş tarihi başlangıçtan önce olamaz")
        if (self.bitis - self.baslangic).days + 1 > EN_COK_GUN:
            raise ValueError(f"Aralık en çok {EN_COK_GUN} gün olabilir")
        return self


class UretYanit(BaseModel):
    olusturulan: int


class OturumGrup(BaseModel):
    id: uuid.UUID
    ad: str


class OturumAntrenor(BaseModel):
    id: uuid.UUID
    ad_soyad: str
    foto_var: bool = False


class OturumOzet(BaseModel):
    id: uuid.UUID
    tarih: date
    baslangic: time
    bitis: time
    durum: OturumDurum
    grup: OturumGrup
    antrenor: OturumAntrenor | None
    ogrenci_sayisi: int
    yoklama_alindi: bool


class OturumOgrenci(BaseModel):
    ogrenci_id: uuid.UUID
    ad: str
    soyad: str
    foto_var: bool
    telafi_mi: bool
    yoklama: YoklamaDurum | None
    # Yalnız gelmedi için; eski kayıtlarda boş olabilir. Açıklama iç nottur (antrenör ve yönetici görür).
    sebep: DevamsizlikSebebi | None = None
    aciklama: str | None = None
    bakiye: DersHakki


class OturumDetay(OturumOzet):
    ogrenciler: list[OturumOgrenci]
    # Yoklamanın ilk kaydından 60 dk sonrası; hiç kaydedilmediyse boş. `kilitli` sunucu saatine göre hesaplanır
    # (antrenör için değişiklik engeli; yönetici kilitli yoklamayı denetim kaydıyla düzeltebilir).
    kilit_zamani: datetime | None = None
    kilitli: bool = False


class IptalGirdi(BaseModel):
    neden: str | None = Field(default=None, max_length=200)


class YoklamaGirdi(BaseModel):
    """Gelmedi için `sebep` zorunludur, geldi için gönderilmez (uç nokta 422 ile anlaşılır mesaj verir).
    `aciklama` her gönderimde öğrencinin güncel notudur: gönderilmezse silinir."""

    ogrenci_id: uuid.UUID
    durum: YoklamaDurum
    sebep: DevamsizlikSebebi | None = None
    aciklama: str | None = Field(default=None, max_length=ACIKLAMA_EN_COK)

    @field_validator("aciklama", mode="before")
    @classmethod
    def _kirp(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class HareketOturum(BaseModel):
    tarih: date
    grup_ad: str


class HareketYanit(BaseModel):
    id: int
    zaman: datetime
    sayac: Sayac
    miktar: int
    tur: HareketTuru
    neden: str | None
    son_kullanma: date | None = None
    oturum: HareketOturum | None


class DersHakkiYanit(DersHakki):
    hareketler: list[HareketYanit]



class DuzeltmeGirdi(BaseModel):
    sayac: Sayac
    miktar: int = Field(ge=-50, le=50)
    neden: str = Field(min_length=3, max_length=500)

    @field_validator("neden", mode="before")
    @classmethod
    def _kirp(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("miktar")
    @classmethod
    def _sifir_degil(cls, v):
        if v == 0:
            raise ValueError("Miktar sıfır olamaz")
        return v


class TelafiAdayi(BaseModel):
    oturum: OturumOzet
    bos_yer: int


class TelafiPlanGirdi(BaseModel):
    ogrenci_id: uuid.UUID


class TelafiPlanYanit(BaseModel):
    oturum_id: uuid.UUID
    tarih: date
    baslangic: time
    bitis: time
    grup: OturumGrup
    yoklama: YoklamaDurum | None
