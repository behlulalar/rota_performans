import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_kolon


class YoklamaDurum(str, enum.Enum):
    geldi = "geldi"
    gelmedi = "gelmedi"


class Sayac(str, enum.Enum):
    normal = "normal"
    telafi = "telafi"


class HareketTuru(str, enum.Enum):
    paket_yuklemesi = "paket_yuklemesi"
    ders_kullanimi = "ders_kullanimi"
    devamsizlik = "devamsizlik"
    telafi_kullanimi = "telafi_kullanimi"
    manuel_duzeltme = "manuel_duzeltme"
    iptal = "iptal"


class Yoklama(Base):
    __tablename__ = "yoklama"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oturum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ders_oturumu.id", ondelete="CASCADE"), index=True
    )
    ogrenci_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ogrenci.id", ondelete="RESTRICT"), index=True
    )
    durum: Mapped[YoklamaDurum] = mapped_column(enum_kolon(YoklamaDurum))
    # Öğrenci bu derse kendi grubu için değil, telafi hakkıyla geldi.
    telafi_mi: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    isaretleyen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )
    zaman: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # "Gelmedi" için telafi hakkı işaretlemeden 1 saat sonra doğar. Arka plan işi bu alanlara bakar.
    hareket_planli_zaman: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hareket_islendi: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    __table_args__ = (
        UniqueConstraint("oturum_id", "ogrenci_id", name="uq_yoklama_oturum_ogrenci"),
        # Arka plan işinin "işlenecekleri bul" sorgusu için küçük, hızlı indeks.
        Index(
            "ix_yoklama_islenecek",
            "hareket_planli_zaman",
            postgresql_where=text("NOT hareket_islendi AND hareket_planli_zaman IS NOT NULL"),
        ),
    )


class DersHakkiHareketi(Base):
    """Ders hakkı defteri. Kayıtlar değiştirilmez ve silinmez, düzeltme yeni bir kayıtla yapılır.
    Bakiye, hareketlerin toplamıdır."""

    __tablename__ = "ders_hakki_hareketi"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ogrenci_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ogrenci.id", ondelete="RESTRICT"), index=True
    )
    sayac: Mapped[Sayac] = mapped_column(enum_kolon(Sayac))
    miktar: Mapped[int] = mapped_column(Integer)
    tur: Mapped[HareketTuru] = mapped_column(enum_kolon(HareketTuru))
    yoklama_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("yoklama.id", ondelete="RESTRICT"), index=True
    )
    ogrenci_paketi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ogrenci_paketi.id", ondelete="RESTRICT"), index=True
    )
    # Bu kayıt başka bir hareketi geri alıyorsa onun kimliği (tur = iptal).
    iptal_edilen_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ders_hakki_hareketi.id", ondelete="RESTRICT")
    )
    neden: Mapped[str | None] = mapped_column(Text)
    olusturan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="RESTRICT")
    )
    zaman: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    # Telafi son kullanma kuralı belli olunca doldurulur.
    son_kullanma: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint("miktar <> 0", name="miktar_sifir_degil"),
        CheckConstraint("(tur = 'iptal') = (iptal_edilen_id IS NOT NULL)", name="iptal_baglantisi"),
        CheckConstraint("tur <> 'manuel_duzeltme' OR (neden IS NOT NULL AND length(trim(neden)) > 0)", name="duzeltme_nedeni"),
        # Aynı yoklama aynı sayaca aynı türde ikinci kez hareket yazamaz (arka plan işi tekrar çalışsa bile).
        Index(
            "uq_hareket_yoklama_tur_sayac",
            "yoklama_id",
            "tur",
            "sayac",
            unique=True,
            postgresql_where=text("yoklama_id IS NOT NULL AND tur <> 'iptal'"),
        ),
        # Bir paket yalnızca bir kez yüklenir.
        Index(
            "uq_hareket_paket_yuklemesi",
            "ogrenci_paketi_id",
            unique=True,
            postgresql_where=text("tur = 'paket_yuklemesi'"),
        ),
        # Bir hareket yalnızca bir kez geri alınabilir.
        Index(
            "uq_hareket_tek_iptal",
            "iptal_edilen_id",
            unique=True,
            postgresql_where=text("iptal_edilen_id IS NOT NULL"),
        ),
    )


# Defterin değiştirilemezliği uygulama koduna değil, veritabanına bırakılır.
# (Alembic otomatik üretimi tetikleyici oluşturmaz, aynı SQL geçiş dosyasında da vardır.)
DEFTER_FONKSIYON_SQL = (
    "CREATE OR REPLACE FUNCTION ders_hakki_degistirilemez() RETURNS trigger AS $$ "
    "BEGIN RAISE EXCEPTION 'ders_hakki_hareketi kayitlari degistirilemez ve silinemez'; END; "
    "$$ LANGUAGE plpgsql"
)
DEFTER_TETIKLEYICI_SQL = (
    "CREATE TRIGGER ders_hakki_hareketi_degistirilemez BEFORE UPDATE OR DELETE ON ders_hakki_hareketi "
    "FOR EACH ROW EXECUTE FUNCTION ders_hakki_degistirilemez()"
)
event.listen(DersHakkiHareketi.__table__, "after_create", DDL(DEFTER_FONKSIYON_SQL).execute_if(dialect="postgresql"))
event.listen(DersHakkiHareketi.__table__, "after_create", DDL(DEFTER_TETIKLEYICI_SQL).execute_if(dialect="postgresql"))
