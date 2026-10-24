import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Rol(str, enum.Enum):
    admin = "admin"
    antrenor = "antrenor"
    veli = "veli"
    ogrenci = "ogrenci"


class Kullanici(Base):
    __tablename__ = "kullanici"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rol: Mapped[Rol] = mapped_column(Enum(Rol, native_enum=False, length=16))
    # Telefon veya e-posta. Küçük harfe çevrilmiş ve kırpılmış saklanır.
    giris: Mapped[str] = mapped_column(String(255), unique=True)
    sifre_ozeti: Mapped[str] = mapped_column(String(255))
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    basarisiz_deneme: Mapped[int] = mapped_column(Integer, default=0)
    kilit_bitis: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    son_giris: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Oturum(Base):
    """Yenileme (refresh) belirteci oturumu. Belirtecin kendisi değil, özeti saklanır."""

    __tablename__ = "oturum"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kullanici_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="CASCADE"), index=True
    )
    token_ozeti: Mapped[str] = mapped_column(String(64), unique=True)
    bitis: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    iptal: Mapped[bool] = mapped_column(Boolean, default=False)
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DenetimKaydi(Base):
    """Kim, ne zaman, ne yaptı. Kişisel veri ve parola içermez."""

    __tablename__ = "denetim_kaydi"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kullanici_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL"), index=True
    )
    islem: Mapped[str] = mapped_column(String(64), index=True)
    hedef_tur: Mapped[str | None] = mapped_column(String(64))
    hedef_id: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(45))
    detay: Mapped[dict | None] = mapped_column(JSONB)
    zaman: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
