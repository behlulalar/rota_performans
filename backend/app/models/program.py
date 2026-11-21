import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_kolon


class OturumDurum(str, enum.Enum):
    planli = "planli"
    yapildi = "yapildi"
    iptal = "iptal"


class Antrenor(Base):
    __tablename__ = "antrenor"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kullanici_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL"), unique=True
    )
    ad_soyad: Mapped[str] = mapped_column(String(200))
    telefon: Mapped[str | None] = mapped_column(String(32))
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # Profil fotoğrafı depolama anahtarı (yalnız yönetici yükler); yoksa baş harfler gösterilir.
    foto_anahtar: Mapped[str | None] = mapped_column(String(255))
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AntrenorFotoRizasi(Base):
    """Antrenörün fotoğraf kullanımı rızası. Aktif rıza: geri_cekildi boş olan kayıt (en fazla bir tane)."""

    __tablename__ = "antrenor_foto_rizasi"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    antrenor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("antrenor.id", ondelete="CASCADE"), index=True
    )
    verildi: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    geri_cekildi: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kaydeden_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )
    geri_ceken_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index(
            "uq_antrenor_foto_rizasi_aktif", "antrenor_id", unique=True, postgresql_where=text("geri_cekildi IS NULL")
        ),
    )


class Grup(Base):
    """Takım / ders grubu."""

    __tablename__ = "grup"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ad: Mapped[str] = mapped_column(String(100))
    antrenor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("antrenor.id", ondelete="SET NULL"), index=True
    )
    kontenjan: Mapped[int] = mapped_column(Integer)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("kontenjan > 0", name="kontenjan_pozitif"),)


class GrupProgrami(Base):
    """Haftalık yineleyen ders slotu. Bir giriş hakkı 90 dakikadır, süre kuralı uygulamadadır."""

    __tablename__ = "grup_programi"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grup_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grup.id", ondelete="CASCADE"))
    gun: Mapped[int] = mapped_column(SmallInteger)  # 1 = pazartesi ... 7 = pazar
    baslangic: Mapped[time] = mapped_column(Time)
    bitis: Mapped[time] = mapped_column(Time)

    __table_args__ = (
        CheckConstraint("gun BETWEEN 1 AND 7", name="gun_araligi"),
        CheckConstraint("bitis > baslangic", name="saat_sirasi"),
        UniqueConstraint("grup_id", "gun", "baslangic", name="uq_grup_programi_slot"),
    )


class OgrenciGrup(Base):
    __tablename__ = "ogrenci_grup"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ogrenci_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ogrenci.id", ondelete="CASCADE"), index=True
    )
    grup_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grup.id", ondelete="CASCADE"), index=True)
    baslangic: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    bitis: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint("bitis IS NULL OR bitis >= baslangic", name="tarih_sirasi"),
        # Aynı öğrenci aynı gruba aynı anda iki kez kayıtlı olamaz.
        Index("uq_ogrenci_grup_acik", "ogrenci_id", "grup_id", unique=True, postgresql_where=text("bitis IS NULL")),
    )


class DersOturumu(Base):
    """Programdan üretilen somut ders (tarihli). Yoklama bunun üzerine alınır."""

    __tablename__ = "ders_oturumu"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grup_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grup.id", ondelete="CASCADE"))
    grup_programi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grup_programi.id", ondelete="SET NULL")
    )
    tarih: Mapped[date] = mapped_column(Date)
    baslangic: Mapped[time] = mapped_column(Time)
    bitis: Mapped[time] = mapped_column(Time)
    # Normal antrenörden farklı biri girerse (yerine bakma).
    antrenor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("antrenor.id", ondelete="SET NULL")
    )
    durum: Mapped[OturumDurum] = mapped_column(enum_kolon(OturumDurum), default=OturumDurum.planli)
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Yoklamanın İLK kaydedildiği an (sonraki düzeltmelerde değişmez). Antrenör için kilit süresi buradan sayılır.
    yoklama_ilk_kayit: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("bitis > baslangic", name="saat_sirasi"),
        UniqueConstraint("grup_id", "tarih", "baslangic", name="uq_ders_oturumu_slot"),
        Index("ix_ders_oturumu_tarih", "tarih"),
        Index("ix_ders_oturumu_antrenor_tarih", "antrenor_id", "tarih"),
    )


class TelafiPlani(Base):
    """Öğrencinin kendi grubu dışındaki bir derse telafi için eklenmesi."""

    __tablename__ = "telafi_plani"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oturum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ders_oturumu.id", ondelete="CASCADE"), index=True
    )
    ogrenci_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ogrenci.id", ondelete="CASCADE"), index=True
    )
    olusturan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kullanici.id", ondelete="SET NULL")
    )
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("oturum_id", "ogrenci_id", name="uq_telafi_plani_oturum_ogrenci"),)
