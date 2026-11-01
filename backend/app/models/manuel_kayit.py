import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_kolon
from app.models.paket import OdemeYontemi


class ManuelKayitTuru(str, enum.Enum):
    gelir = "gelir"
    gider = "gider"


class ManuelKayit(Base):
    """Öğrenci ödemesi dışındaki gelir/gider (ör. kamp geliri, havuz kirası). Tutar her zaman pozitif;
    yönü `tur` belirler. Silinmez: yanlış kayıt iptal edilir ve toplamlara girmez."""

    __tablename__ = "manuel_kayit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tur: Mapped[ManuelKayitTuru] = mapped_column(enum_kolon(ManuelKayitTuru))
    tarih: Mapped[date] = mapped_column(Date, index=True)
    tutar: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    yontem: Mapped[OdemeYontemi] = mapped_column(enum_kolon(OdemeYontemi))
    aciklama: Mapped[str] = mapped_column(String(200))
    olusturan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    iptal_zamani: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    iptal_nedeni: Mapped[str | None] = mapped_column(Text)
    iptal_eden_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint("tutar > 0", name="tutar_pozitif"),
        CheckConstraint("(iptal_zamani IS NULL) = (iptal_nedeni IS NULL)", name="iptal_alanlari_birlikte"),
    )
