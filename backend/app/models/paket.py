import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_kolon


class PaketTuru(str, enum.Enum):
    aylik = "aylik"
    uc_aylik = "uc_aylik"
    alti_aylik = "alti_aylik"
    yillik = "yillik"
    ozel_ders = "ozel_ders"


class OgrenciPaketiDurum(str, enum.Enum):
    odeme_bekliyor = "odeme_bekliyor"
    odendi = "odendi"
    iptal = "iptal"


class OdemeYontemi(str, enum.Enum):
    nakit = "nakit"
    havale_eft = "havale_eft"
    pos = "pos"
    diger = "diger"


class Paket(Base):
    __tablename__ = "paket"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ad: Mapped[str] = mapped_column(String(100))
    tur: Mapped[PaketTuru] = mapped_column(enum_kolon(PaketTuru))
    ders_sayisi: Mapped[int] = mapped_column(Integer)
    sure_ay: Mapped[int] = mapped_column(Integer)
    varsayilan_fiyat: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("ders_sayisi > 0", name="ders_sayisi_pozitif"),
        CheckConstraint("sure_ay > 0", name="sure_pozitif"),
        CheckConstraint("varsayilan_fiyat >= 0", name="fiyat_negatif_degil"),
    )


class OgrenciPaketi(Base):
    """Öğrenciye atanan paket. Aidat satırı budur."""

    __tablename__ = "ogrenci_paketi"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ogrenci_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ogrenci.id", ondelete="RESTRICT"), index=True
    )
    paket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("paket.id", ondelete="RESTRICT"))
    # Paketin o günkü hali kopyalanır: paket sonradan değişse de geçmiş kayıt bozulmaz.
    ders_sayisi: Mapped[int] = mapped_column(Integer)
    liste_fiyati: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    uygulanan_fiyat: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fiyat_ozel_mi: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    fiyat_degistiren_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )
    baslangic: Mapped[date | None] = mapped_column(Date)
    bitis: Mapped[date | None] = mapped_column(Date)
    durum: Mapped[OgrenciPaketiDurum] = mapped_column(
        enum_kolon(OgrenciPaketiDurum), default=OgrenciPaketiDurum.odeme_bekliyor
    )
    olusturan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("ders_sayisi > 0", name="ders_sayisi_pozitif"),
        CheckConstraint("liste_fiyati >= 0 AND uygulanan_fiyat >= 0", name="fiyat_negatif_degil"),
        # Fiyat listeden farklıysa "özel fiyat" işaretlenmiş olmalı.
        CheckConstraint("fiyat_ozel_mi OR uygulanan_fiyat = liste_fiyati", name="ozel_fiyat_isareti"),
        CheckConstraint("bitis IS NULL OR baslangic IS NULL OR bitis >= baslangic", name="tarih_sirasi"),
    )


class Odeme(Base):
    __tablename__ = "odeme"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ogrenci_paketi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ogrenci_paketi.id", ondelete="RESTRICT"), index=True
    )
    tutar: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    tarih: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    yontem: Mapped[OdemeYontemi] = mapped_column(enum_kolon(OdemeYontemi))
    aciklama: Mapped[str | None] = mapped_column(Text)
    olusturan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Ödeme geri alınırsa kayıt silinmez; iptal alanları dolar ve toplamlara girmez.
    iptal_zamani: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    iptal_nedeni: Mapped[str | None] = mapped_column(Text)
    iptal_eden_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint("tutar > 0", name="tutar_pozitif"),
        CheckConstraint("(iptal_zamani IS NULL) = (iptal_nedeni IS NULL)", name="iptal_alanlari_birlikte"),
    )
