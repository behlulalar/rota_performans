"""Ders hakkı defteri iş mantığı. Uç noktalar ve arka plan işçisi buradan çağırır.

Defter satırları değiştirilmez: yoklama düzeltilirse eski hareketler `iptal` satırıyla geri alınır,
yeni durum yeni bir yoklama sürümüyle yazılır. Çağıran işlemi commit eder."""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.program import DersOturumu, OturumDurum, TelafiPlani
from app.models.yoklama import DersHakkiHareketi, HareketTuru, Sayac, Yoklama, YoklamaDurum

from app.oturumlar import bugun

DEVAMSIZLIK_BEKLEME = timedelta(hours=1)


async def bakiyeler(session: AsyncSession, ogrenci_idleri: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    """Birden çok öğrencinin bakiyesini tek sorguda verir. Bakiye negatife düşebilir."""
    sonuc = {i: {"normal": 0, "telafi": 0} for i in ogrenci_idleri}
    if not ogrenci_idleri:
        return sonuc
    satirlar = await session.execute(
        select(DersHakkiHareketi.ogrenci_id, DersHakkiHareketi.sayac, func.sum(DersHakkiHareketi.miktar))
        .where(DersHakkiHareketi.ogrenci_id.in_(ogrenci_idleri))
        .group_by(DersHakkiHareketi.ogrenci_id, DersHakkiHareketi.sayac)
    )
    for ogrenci_id, sayac, toplam in satirlar.all():
        sonuc[ogrenci_id][sayac.value] = int(toplam)
    return sonuc


async def bakiye(session: AsyncSession, ogrenci_id: uuid.UUID) -> dict[str, int]:
    return (await bakiyeler(session, [ogrenci_id]))[ogrenci_id]


async def kullanilabilir_telafi(session: AsyncSession, ogrenci_id: uuid.UUID) -> int:
    """Telafi bakiyesi eksi, ileri tarihli (bugün dahil) planlanmış ve yoklaması alınmamış telafi dersleri."""
    planli = (
        await session.execute(
            select(func.count())
            .select_from(TelafiPlani)
            .join(DersOturumu, DersOturumu.id == TelafiPlani.oturum_id)
            .where(
                TelafiPlani.ogrenci_id == ogrenci_id,
                DersOturumu.tarih >= bugun(),
                DersOturumu.durum != OturumDurum.iptal,
                ~exists().where(Yoklama.oturum_id == DersOturumu.id, Yoklama.ogrenci_id == ogrenci_id),
            )
        )
    ).scalar_one()
    return (await bakiye(session, ogrenci_id))["telafi"] - planli


def _hareket(yoklama: Yoklama, sayac: Sayac, miktar: int, tur: HareketTuru) -> DersHakkiHareketi:
    return DersHakkiHareketi(
        ogrenci_id=yoklama.ogrenci_id,
        sayac=sayac,
        miktar=miktar,
        tur=tur,
        yoklama_id=yoklama.id,
        yoklama_surum=yoklama.surum,
        olusturan_id=yoklama.isaretleyen_id,
    )


async def _acik_hareketleri_iptal_et(session: AsyncSession, yoklama: Yoklama) -> None:
    """Yoklamanın henüz geri alınmamış tüm hareketleri için ters kayıt yazar."""
    geri_alinan = select(DersHakkiHareketi.iptal_edilen_id).where(DersHakkiHareketi.iptal_edilen_id.is_not(None))
    acik = (
        await session.execute(
            select(DersHakkiHareketi)
            .where(
                DersHakkiHareketi.yoklama_id == yoklama.id,
                DersHakkiHareketi.tur != HareketTuru.iptal,
                DersHakkiHareketi.id.not_in(geri_alinan),
            )
            .order_by(DersHakkiHareketi.id)
        )
    ).scalars()
    for h in acik:
        session.add(
            DersHakkiHareketi(
                ogrenci_id=h.ogrenci_id,
                sayac=h.sayac,
                miktar=-h.miktar,
                tur=HareketTuru.iptal,
                iptal_edilen_id=h.id,
                neden="Yoklama düzeltildi",
                olusturan_id=yoklama.isaretleyen_id,
            )
        )


def _durumun_etkisi(session: AsyncSession, yoklama: Yoklama, simdi: datetime) -> None:
    """Yeni durumun hareketini yazar ya da 1 saatlik beklemeyi planlar."""
    if yoklama.durum == YoklamaDurum.geldi:
        if yoklama.telafi_mi:
            session.add(_hareket(yoklama, Sayac.telafi, -1, HareketTuru.telafi_kullanimi))
        else:
            session.add(_hareket(yoklama, Sayac.normal, -1, HareketTuru.ders_kullanimi))
        yoklama.hareket_planli_zaman = None
        yoklama.hareket_islendi = True
    elif yoklama.telafi_mi:
        # Telafi dersine gelmedi: hak doğmaz ve düşmez, yalnızca planlanmaz.
        yoklama.hareket_planli_zaman = None
        yoklama.hareket_islendi = True
    else:
        yoklama.hareket_planli_zaman = simdi + DEVAMSIZLIK_BEKLEME
        yoklama.hareket_islendi = False


async def yoklama_olustur(
    session: AsyncSession,
    *,
    oturum_id: uuid.UUID,
    ogrenci_id: uuid.UUID,
    durum: YoklamaDurum,
    telafi_mi: bool,
    isaretleyen_id: uuid.UUID | None,
    simdi: datetime,
) -> Yoklama:
    """İlk kez yoklama alınan öğrenci için kayıt ve (varsa) hareket oluşturur."""
    yoklama = Yoklama(
        id=uuid.uuid4(),
        oturum_id=oturum_id,
        ogrenci_id=ogrenci_id,
        durum=durum,
        telafi_mi=telafi_mi,
        isaretleyen_id=isaretleyen_id,
        zaman=simdi,
        surum=0,
        hareket_islendi=False,
    )
    session.add(yoklama)
    await session.flush()
    _durumun_etkisi(session, yoklama, simdi)
    await session.flush()
    return yoklama


async def yoklama_uygula(
    session: AsyncSession,
    yoklama: Yoklama,
    yeni_durum: YoklamaDurum,
    isaretleyen_id: uuid.UUID | None,
    simdi: datetime,
) -> None:
    """Var olan yoklamanın durumunu değiştirir. Eski hareketler iptal edilir, sürüm artar."""
    if yoklama.durum == yeni_durum:
        return
    yoklama.isaretleyen_id = isaretleyen_id
    await _acik_hareketleri_iptal_et(session, yoklama)
    yoklama.surum += 1
    yoklama.durum = yeni_durum
    yoklama.zaman = simdi
    _durumun_etkisi(session, yoklama, simdi)
    await session.flush()


async def bekleyen_devamsizliklari_isle(session: AsyncSession, simdi: datetime) -> int:
    """Planlı zamanı gelmiş `gelmedi` yoklamalarının devamsızlık hareketini yazar.
    Birden çok işçi çalışsa da aynı yoklama iki kez işlenmez. Dönen sayı: hareket yazılan yoklama sayısı."""
    bekleyenler = (
        await session.execute(
            select(Yoklama)
            .where(
                Yoklama.hareket_islendi.is_(False),
                Yoklama.hareket_planli_zaman.is_not(None),
                Yoklama.hareket_planli_zaman <= simdi,
            )
            .order_by(Yoklama.hareket_planli_zaman)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    yazilan = 0
    for y in bekleyenler:
        # Süre içinde düzeltildiyse (artık gelmedi değilse) hak doğmaz.
        if y.durum == YoklamaDurum.gelmedi and not y.telafi_mi:
            session.add(_hareket(y, Sayac.normal, -1, HareketTuru.devamsizlik))
            session.add(_hareket(y, Sayac.telafi, 1, HareketTuru.devamsizlik))
            yazilan += 1
        y.hareket_islendi = True
    await session.flush()
    return yazilan
