import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.metin import Baslik

from app.models.kullanici import Rol
from app.models.ogrenci import OgrenciDurum
from app.models.paket import OdemeYontemi, OgrenciPaketiDurum
from app.models.program import OturumDurum
from app.models.yoklama import DevamsizlikSebebi, HareketTuru, Sayac, YoklamaDurum
from app.schemas.ogrenci import DersHakkiDetay
from app.schemas.paket import Tutar


class VeliGrup(BaseModel):
    id: uuid.UUID
    ad: str


class VeliDers(BaseModel):
    """Çocuğun tarihli bir dersi: kendi grubundan ya da telafi için eklendiği ders."""

    oturum_id: uuid.UUID
    tarih: date
    baslangic: time
    bitis: time
    grup_ad: str
    telafi_mi: bool
    durum: OturumDurum
    yoklama: YoklamaDurum | None = None
    # Gelmedi sebebi. Antrenörün iç notu (açıklama) veliye hiçbir zaman gönderilmez.
    sebep: DevamsizlikSebebi | None = None


class VeliProgramSatiri(BaseModel):
    grup_ad: str
    gun: int
    baslangic: time
    bitis: time


class CocukOzet(BaseModel):
    id: uuid.UUID
    ad: str
    soyad: str
    foto_var: bool
    durum: OgrenciDurum
    gruplar: list[VeliGrup]
    ders_hakki: DersHakkiDetay
    siradaki_ders: VeliDers | None
    odeme_bekleyen: int
    # Ödenmiş paket var ama kalan ders kalmadı: veliye "ders hakkınız bitti" uyarısı çıkar.
    ders_hakki_bitti: bool = False


class VeliOdeme(BaseModel):
    tarih: date
    tutar: Tutar
    yontem: OdemeYontemi
    iptal: bool


class VeliPaket(BaseModel):
    id: uuid.UUID
    paket_adi: str
    ders_sayisi: int
    uygulanan_fiyat: Tutar
    toplam_odenen: Tutar
    durum: OgrenciPaketiDurum
    baslangic: date | None
    bitis: date | None
    olusturma: datetime
    odemeler: list[VeliOdeme]


class VeliHareket(BaseModel):
    zaman: datetime
    sayac: Sayac
    miktar: int
    tur: HareketTuru
    son_kullanma: date | None = None


class DersOzeti(BaseModel):
    """Tüm deftere bakarak hesaplanan, geri alınmış kayıtları saymayan özet."""

    toplam: int  # paketlerle yüklenen ve kulübün eklediği/düzelttiği toplam ders hakkı
    katildi: int
    devamsiz: int
    kalan: int
    telafi_dogan: int
    telafi_kullanilan: int
    telafi_yanan: int  # ay sonunda kullanılmadığı için düşen telafi hakları
    telafi_kalan: int


class VeliAntrenor(BaseModel):
    """Veliye yalnız ad ve fotoğraf gösterilir; telefon vb. verilmez."""

    id: uuid.UUID
    ad_soyad: str
    foto_var: bool


class CocukDetay(CocukOzet):
    antrenorler: list[VeliAntrenor] = []
    program: list[VeliProgramSatiri]
    yaklasan_dersler: list[VeliDers]
    gecmis_dersler: list[VeliDers]
    paketler: list[VeliPaket]
    ders_ozeti: DersOzeti
    hareketler: list[VeliHareket]


class Profil(BaseModel):
    giris: str
    rol: Rol
    ad_soyad: str | None
    telefon: str | None


class ProfilGuncelle(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ad_soyad: Baslik = Field(min_length=1, max_length=200)
    telefon: str = Field(min_length=1, max_length=40)


class BildirimTercihleri(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ders_gelmedi: bool = True
    ders_hakki: bool = True
    whatsapp: bool = True
    push: bool = True


class BildirimTercihYaniti(BildirimTercihleri):
    # Hesaba bağlı kişilerden en az birinde WhatsApp izni var mı (arayüz notu için).
    whatsapp_izni_var: bool


class PushAnahtari(BaseModel):
    etkin: bool
    anahtar: str | None = None


class PushAnahtarlari(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=255)


class PushAbonelikGiris(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(min_length=10, max_length=2000)
    keys: PushAnahtarlari
    cihaz: str | None = Field(default=None, max_length=255)

    @field_validator("endpoint")
    @classmethod
    def _https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("Uç nokta https olmalı")
        return v


class PushAbonelikSil(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(min_length=1, max_length=2000)
