from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KulupAyari(Base):
    """Kulüp ayarları: tek satırlık tablo (id her zaman 1). Satır yoksa varsayılanlar geçerlidir."""

    __tablename__ = "kulup_ayari"
    __table_args__ = (
        CheckConstraint("id = 1", name="tek_satir"),
        CheckConstraint("geri_alma_dakika BETWEEN 1 AND 15", name="geri_alma_aralik"),
        CheckConstraint("azaldi_esigi BETWEEN 1 AND 5", name="azaldi_esigi_aralik"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    ad: Mapped[str] = mapped_column(String(120), default="Rota Performans Akademi", server_default="Rota Performans Akademi")
    telefon: Mapped[str | None] = mapped_column(String(20))
    eposta: Mapped[str | None] = mapped_column(String(254))
    adres: Mapped[str | None] = mapped_column(String(500))
    geri_alma_dakika: Mapped[int] = mapped_column(Integer, default=3, server_default=text("3"))
    azaldi_esigi: Mapped[int] = mapped_column(Integer, default=2, server_default=text("2"))
    guncelleme: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
