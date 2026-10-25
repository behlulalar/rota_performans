import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_kolon


class Cinsiyet(str, enum.Enum):
    kadin = "kadin"
    erkek = "erkek"


class KimlikTur(str, enum.Enum):
    tc = "tc"
    pasaport = "pasaport"


class OgrenciDurum(str, enum.Enum):
    aktif = "aktif"
    pasif = "pasif"


class IletisimRolu(str, enum.Enum):
    anne = "anne"
    baba = "baba"
    diger = "diger"
    kendisi = "kendisi"


class RizaTuru(str, enum.Enum):
    aydinlatma = "aydinlatma"
    foto = "foto"
    whatsapp = "whatsapp"


class Ogrenci(Base):
    __tablename__ = "ogrenci"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ad: Mapped[str] = mapped_column(String(100))
    soyad: Mapped[str] = mapped_column(String(100))
    anne_adi: Mapped[str | None] = mapped_column(String(100))
    baba_adi: Mapped[str | None] = mapped_column(String(100))
    dogum_tarihi: Mapped[date] = mapped_column(Date)
    cinsiyet: Mapped[Cinsiyet | None] = mapped_column(enum_kolon(Cinsiyet))

    # T.C. kimlik veya pasaport numarası yalnızca numara olarak tutulur (görsel/fotokopi saklanmaz).
    # Şifreli değer okunmak için, özet (HMAC) tekrar eden kayıtları yakalamak için kullanılır.
    kimlik_tur: Mapped[KimlikTur] = mapped_column(enum_kolon(KimlikTur), default=KimlikTur.tc)
    kimlik_no_sifreli: Mapped[bytes | None] = mapped_column(LargeBinary)
    kimlik_no_ozet: Mapped[str | None] = mapped_column(String(64), unique=True)

    telefon: Mapped[str | None] = mapped_column(String(32))
    foto_anahtar: Mapped[str | None] = mapped_column(String(255))
    durum: Mapped[OgrenciDurum] = mapped_column(enum_kolon(OgrenciDurum), default=OgrenciDurum.aktif)
    kayit_tarihi: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    # Reşit öğrencinin kendi hesabı.
    kullanici_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL"), unique=True
    )
    # Test ve duman testi verisini raporlardan ayırmak için.
    sentetik: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    guncelleme: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("(kimlik_no_sifreli IS NULL) = (kimlik_no_ozet IS NULL)", name="kimlik_cifti"),
        Index("ix_ogrenci_soyad_ad", "soyad", "ad"),
        Index("ix_ogrenci_durum", "durum"),
    )


class IletisimKisisi(Base):
    """Formdaki anne / baba / diğer-kendisi telefonları. Veli kavramının karşılığı."""

    __tablename__ = "iletisim_kisisi"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ogrenci_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ogrenci.id", ondelete="CASCADE"), index=True
    )
    rol: Mapped[IletisimRolu] = mapped_column(enum_kolon(IletisimRolu))
    ad_soyad: Mapped[str] = mapped_column(String(200))
    telefon: Mapped[str] = mapped_column(String(32))
    # Panel hesabı yalnızca birincil kişide olur. Kardeşlerde aynı hesap birden çok satıra bağlanır.
    kullanici_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL"), index=True
    )
    # Öğrenciye ait tüm bildirimler yalnızca birincil kişiye gider.
    birincil: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    whatsapp_izni: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    push_izni: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("kullanici_id IS NULL OR birincil", name="hesap_yalniz_birincilde"),
        # Öğrenci başına en çok bir birincil kişi. "En az bir" kuralı kayıt servisinde zorunlu tutulur.
        Index("uq_iletisim_kisisi_tek_birincil", "ogrenci_id", unique=True, postgresql_where=text("birincil")),
    )


class Riza(Base):
    __tablename__ = "riza"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ogrenci_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ogrenci.id", ondelete="CASCADE"), index=True
    )
    iletisim_kisisi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iletisim_kisisi.id", ondelete="SET NULL")
    )
    tur: Mapped[RizaTuru] = mapped_column(enum_kolon(RizaTuru))
    verildi: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    geri_cekildi: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kaydeden_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )
