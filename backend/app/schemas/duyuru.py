import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.bildirim import BildirimDurum, BildirimKanal
from app.models.duyuru import DuyuruHedefTuru

EN_COK_GRUP = 50


class DuyuruHedef(BaseModel):
    tur: DuyuruHedefTuru
    oturum_id: uuid.UUID | None = None
    grup_idleri: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def _tutarli(self):
        if self.tur == DuyuruHedefTuru.oturum and self.oturum_id is None:
            raise ValueError("Ders oturumu seçin")
        if self.tur == DuyuruHedefTuru.grup:
            if not self.grup_idleri:
                raise ValueError("En az bir grup seçin")
            if len(set(self.grup_idleri)) > EN_COK_GRUP:
                raise ValueError(f"En çok {EN_COK_GRUP} grup seçilebilir")
        return self


class DuyuruKanallari(BaseModel):
    push: bool = True
    whatsapp: bool = False


class OnizlemeGirdi(BaseModel):
    hedef: DuyuruHedef
    kanallar: DuyuruKanallari = DuyuruKanallari()


class OnizlemeYanit(BaseModel):
    ogrenci: int
    alici: int  # tekilleştirilmiş birincil kişi sayısı
    push_alacak: int
    push_yok: int  # alıcı - push_alacak (hesap/cihaz yok ya da tercih kapalı)
    whatsapp_izinli: int


class DuyuruGirdi(BaseModel):
    baslik: str = Field(min_length=1, max_length=120)
    metin: str = Field(min_length=1, max_length=1000)
    hedef: DuyuruHedef
    kanallar: DuyuruKanallari = DuyuruKanallari()
    # True: alıcı push ile de ulaşılsa WhatsApp'a yine gönderilir (ders iptali gibi önemli duyurular).
    her_iki_kanal: bool = False

    @field_validator("baslik", "metin")
    @classmethod
    def _kirp(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Boş olamaz")
        return v


class KanalIstatistigi(BaseModel):
    toplam: int = 0
    gonderildi: int = 0
    bekliyor: int = 0
    hata: int = 0
    iptal: int = 0


class DuyuruIstatistik(BaseModel):
    push: KanalIstatistigi = KanalIstatistigi()
    whatsapp: KanalIstatistigi = KanalIstatistigi()


class DuyuruOzet(BaseModel):
    id: uuid.UUID
    baslik: str
    metin: str
    olusturma: datetime
    hedef_tur: DuyuruHedefTuru
    hedef_ozet: str
    oturum_id: uuid.UUID | None
    kanallar: DuyuruKanallari
    her_iki_kanal: bool
    istatistik: DuyuruIstatistik


class DuyuruAlicisi(BaseModel):
    bildirim_id: int
    ogrenci_ad: str
    alici_ad: str
    kanal: BildirimKanal
    durum: BildirimDurum
    hata: str | None
    gonderim_zamani: datetime | None


class DuyuruDetay(DuyuruOzet):
    alicilar: list[DuyuruAlicisi]
