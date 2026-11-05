import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_kolon


class DuyuruHedefTuru(str, enum.Enum):
    oturum = "oturum"
    grup = "grup"
    tum = "tum"


class Duyuru(Base):
    """Yöneticinin elle yazdığı duyuru. Metin kulübün kendi mesajıdır, bu yüzden saklanır;
    alıcılar ise `bildirim` satırlarıdır (kişisel veri duyuruda tutulmaz)."""

    __tablename__ = "duyuru"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    baslik: Mapped[str] = mapped_column(String(120))
    metin: Mapped[str] = mapped_column(Text)  # en çok 1000 karakter (şema doğrular)
    hedef_tur: Mapped[DuyuruHedefTuru] = mapped_column(enum_kolon(DuyuruHedefTuru))
    # oturum: {"oturum_id": "..."}, grup: {"grup_idleri": ["...", ...]}, tum: {}
    hedef: Mapped[dict] = mapped_column(JSONB, default=dict)
    kanal_push: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    kanal_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # True: push da gitse WhatsApp'a yine gönderilir (ders iptali gibi önemli duyurular). False: push ile ulaşılan
    # kişiye WhatsApp gönderilmez (ayar `wa_push_varsa_atla` açıksa).
    her_iki_kanal: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    olusturan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )
    # Ders iptali gibi bir oturumla ilgili duyuruysa o oturum.
    oturum_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ders_oturumu.id", ondelete="SET NULL"), index=True
    )
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
