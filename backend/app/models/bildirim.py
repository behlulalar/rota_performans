import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_kolon


class BildirimKanal(str, enum.Enum):
    whatsapp = "whatsapp"
    push = "push"


class BildirimDurum(str, enum.Enum):
    bekliyor = "bekliyor"
    gonderildi = "gonderildi"
    hata = "hata"
    iptal = "iptal"


class Bildirim(Base):
    """Giden bildirim kuyruğu. Alıcı her zaman öğrencinin birincil iletişim kişisidir."""

    __tablename__ = "bildirim"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ogrenci_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ogrenci.id", ondelete="CASCADE"), index=True
    )
    alici_iletisim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iletisim_kisisi.id", ondelete="RESTRICT")
    )
    kanal: Mapped[BildirimKanal] = mapped_column(enum_kolon(BildirimKanal))
    # Mesaj metni burada saklanmaz: şablon adı ve kişisel veri içermeyen parametreler tutulur,
    # ad gibi bilgiler gönderim anında kayıttan okunur.
    sablon: Mapped[str] = mapped_column(String(64))
    parametreler: Mapped[dict | None] = mapped_column(JSONB)
    yoklama_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("yoklama.id", ondelete="SET NULL")
    )
    durum: Mapped[BildirimDurum] = mapped_column(enum_kolon(BildirimDurum), default=BildirimDurum.bekliyor)
    # Geri alma penceresi: bu zamandan önce gönderilmez, yoklama düzeltilirse iptal edilir.
    planli_zaman: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    gonderim_zamani: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deneme: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    hata: Mapped[str | None] = mapped_column(Text)
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("deneme >= 0", name="deneme_negatif_degil"),
        Index("ix_bildirim_gonderilecek", "planli_zaman", postgresql_where=text("durum = 'bekliyor'")),
        # Aynı yoklama için aynı kanaldan aynı şablonla ikinci bildirim oluşmaz.
        Index(
            "uq_bildirim_yoklama_kanal_sablon",
            "yoklama_id",
            "kanal",
            "sablon",
            unique=True,
            postgresql_where=text("yoklama_id IS NOT NULL"),
        ),
    )


class PushAbonelik(Base):
    __tablename__ = "push_abonelik"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kullanici_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    cihaz: Mapped[str | None] = mapped_column(String(255))
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    son_kullanim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BildirimTercihi(Base):
    """Veli/öğrenci hesabının bildirim tercihleri. Satır yoksa hepsi açıktır.
    Tercih hesaba aittir: kardeşlerin hepsi için geçerlidir."""

    __tablename__ = "bildirim_tercihi"

    kullanici_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="CASCADE"), primary_key=True
    )
    whatsapp: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    push: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    ders_gelmedi: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    ders_hakki: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    guncelleme: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
