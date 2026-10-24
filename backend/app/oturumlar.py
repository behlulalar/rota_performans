"""Ders oturumu üretimi ve saat dilimi yardımcıları. Uç nokta ve arka plan işçisi ortak kullanır."""
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.program import DersOturumu, Grup, GrupProgrami, OturumDurum

PARCA_BOYUTU = 1000


def simdi() -> datetime:
    return datetime.now(timezone.utc)


YOKLAMA_ERKEN_ACILIS = timedelta(minutes=15)


def yoklama_acilis_zamani(tarih: date, baslangic: time) -> datetime:
    """Antrenörün yoklama alabileceği en erken an: ders başlangıcından 15 dakika önce (kulüp saati)."""
    return datetime.combine(tarih, baslangic, tzinfo=ZoneInfo(settings.saat_dilimi)) - YOKLAMA_ERKEN_ACILIS


def bugun(an: datetime | None = None) -> date:
    """Kulübün saat dilimine göre bugünün tarihi."""
    an = an or simdi()
    return an.astimezone(ZoneInfo(settings.saat_dilimi)).date()


async def oturumlari_uret(session: AsyncSession, baslangic: date, bitis: date) -> int:
    """Aktif grupların haftalık programından [baslangic, bitis] aralığındaki dersleri üretir.
    Var olan oturum tekrar oluşturulmaz. Dönen sayı: yeni oluşturulan oturum sayısı. Çağıran commit eder."""
    if bitis < baslangic:
        return 0
    slotlar = (
        await session.execute(
            select(GrupProgrami).join(Grup, Grup.id == GrupProgrami.grup_id).where(Grup.aktif.is_(True))
        )
    ).scalars().all()
    gunluk: dict[int, list[GrupProgrami]] = {}
    for s in slotlar:
        gunluk.setdefault(s.gun, []).append(s)
    satirlar = []
    gun = baslangic
    while gun <= bitis:
        for s in gunluk.get(gun.isoweekday(), []):
            satirlar.append(
                {
                    "id": uuid.uuid4(),
                    "grup_id": s.grup_id,
                    "grup_programi_id": s.id,
                    "tarih": gun,
                    "baslangic": s.baslangic,
                    "bitis": s.bitis,
                    "durum": OturumDurum.planli,
                }
            )
        gun += timedelta(days=1)
    olusan = 0
    for i in range(0, len(satirlar), PARCA_BOYUTU):
        sonuc = await session.execute(
            pg_insert(DersOturumu)
            .values(satirlar[i : i + PARCA_BOYUTU])
            .on_conflict_do_nothing(index_elements=["grup_id", "tarih", "baslangic"])
            .returning(DersOturumu.id)
        )
        olusan += len(sonuc.all())
    return olusan
