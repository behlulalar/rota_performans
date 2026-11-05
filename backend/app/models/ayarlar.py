from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KulupAyari(Base):
    """Kulüp ayarları: tek satırlık tablo (id her zaman 1). Satır yoksa varsayılanlar geçerlidir."""

    __tablename__ = "kulup_ayari"
    __table_args__ = (
        CheckConstraint("id = 1", name="tek_satir"),
        CheckConstraint("geri_alma_dakika BETWEEN 1 AND 15", name="geri_alma_aralik"),
        CheckConstraint("azaldi_esigi BETWEEN 1 AND 5", name="azaldi_esigi_aralik"),
        CheckConstraint("wa_saatlik_limit BETWEEN 1 AND 200", name="wa_saatlik_limit_aralik"),
        CheckConstraint("wa_gunluk_limit BETWEEN 1 AND 1000", name="wa_gunluk_limit_aralik"),
        CheckConstraint("wa_baslangic_saat BETWEEN 0 AND 23", name="wa_baslangic_saat_aralik"),
        CheckConstraint("wa_bitis_saat BETWEEN 1 AND 24", name="wa_bitis_saat_aralik"),
        CheckConstraint("wa_baslangic_saat < wa_bitis_saat", name="wa_saat_sirasi"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    ad: Mapped[str] = mapped_column(String(120), default="Rota Performans Akademi", server_default="Rota Performans Akademi")
    telefon: Mapped[str | None] = mapped_column(String(20))
    eposta: Mapped[str | None] = mapped_column(String(254))
    adres: Mapped[str | None] = mapped_column(String(500))
    instagram: Mapped[str | None] = mapped_column(String(30))  # kullanıcı adı, @ olmadan
    geri_alma_dakika: Mapped[int] = mapped_column(Integer, default=3, server_default=text("3"))
    azaldi_esigi: Mapped[int] = mapped_column(Integer, default=2, server_default=text("2"))
    # WhatsApp gönderim koruması (docs/bildirim-kurallari.md bölüm 4).
    wa_saatlik_limit: Mapped[int] = mapped_column(Integer, default=50, server_default=text("50"))
    wa_gunluk_limit: Mapped[int] = mapped_column(Integer, default=250, server_default=text("250"))
    wa_baslangic_saat: Mapped[int] = mapped_column(Integer, default=9, server_default=text("9"))
    wa_bitis_saat: Mapped[int] = mapped_column(Integer, default=21, server_default=text("21"))
    wa_push_varsa_atla: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    guncelleme: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
