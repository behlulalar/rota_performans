"""Ders hakkı defteri iş mantığı. Uç noktalar ve arka plan işçisi buradan çağırır.

Defter satırları değiştirilmez: yoklama düzeltilirse eski hareketler `iptal` satırıyla geri alınır,
yeni durum yeni bir yoklama sürümüyle yazılır. Çağıran işlemi commit eder.

Devamsızlık sebebi (1 saatlik bekleme sonunda):
- izinli / raporlu / yarisma (ve sebebi olmayan eski kayıtlar): normal -1, telafi +1; telafi hakkı dersin ayının
  son gününe (İstanbul takvimi) kadar kullanılabilir (`son_kullanma`).
- devamsiz: yalnızca normal -1 ("ders yanar"), telafi doğmaz.
Telafi hakları en eski (son kullanması en yakın) olandan başlayarak tüketilir. Ay sonunda kullanılmayan hak
`telafi_suresi_doldu` hareketiyle düşülür ("hak yanar"); normal sayaca dönmez. Süre dolumu bir uzlaştırmadır
(`telafi_uzlastir`): günlük işçi işi ve her yoklama değişikliği farkı (iki yönde de) yazar."""
import calendar
import logging
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import bildirim
from app.config import settings
from app.models.ogrenci import Ogrenci
from app.models.program import DersOturumu, KatilimTuru, OturumDurum, TelafiPlani
from app.models.yoklama import (
    MAZERETLI_SEBEPLER,
    DersHakkiHareketi,
    DevamsizlikSebebi,
    HareketTuru,
    Sayac,
    Yoklama,
    YoklamaDurum,
)

from app.oturumlar import bugun

DEVAMSIZLIK_BEKLEME = timedelta(hours=1)
log = logging.getLogger("ders_hakki")


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


def ay_sonu(tarih: date) -> date:
    """Tarihin ayının son günü (devamsızlık telafisinin son kullanma günü)."""
    return tarih.replace(day=calendar.monthrange(tarih.year, tarih.month)[1])


def _sira(son: date | None) -> tuple[bool, date]:
    # Süresiz (boş) haklar en sona: önce süresi dolacak olan tüketilir.
    return (son is None, son or date.min)


async def _telafi_satirlari(
    session: AsyncSession, ogrenci_id: uuid.UUID
) -> tuple[list[date | None], list[date], int]:
    """Geri alınmamış telafi hareketleri (iptal satırları ve geri aldıkları kayıtlar birlikte dışarıda kalır).

    Döner: (artı birimlerin son kullanma günleri eskiden yeniye, eksi birimlerin günleri, yazılmış net süre dolumu).
    Eksinin günü: telafi kullanımında dersin tarihi (yoklama geç alınsa da), diğerlerinde kaydın İstanbul günü.
    `telafi_suresi_doldu` satırları eksi sayılmaz, ayrıca toplanır (uzlaştırma bunları yeniden hesaplar)."""
    geri_alinan = select(DersHakkiHareketi.iptal_edilen_id).where(DersHakkiHareketi.iptal_edilen_id.is_not(None))
    gun = func.coalesce(DersOturumu.tarih, func.date(func.timezone(settings.saat_dilimi, DersHakkiHareketi.zaman)))
    satirlar = (
        await session.execute(
            select(DersHakkiHareketi.tur, DersHakkiHareketi.miktar, DersHakkiHareketi.son_kullanma, gun)
            .outerjoin(Yoklama, Yoklama.id == DersHakkiHareketi.yoklama_id)
            .outerjoin(DersOturumu, DersOturumu.id == Yoklama.oturum_id)
            .where(
                DersHakkiHareketi.ogrenci_id == ogrenci_id,
                DersHakkiHareketi.sayac == Sayac.telafi,
                DersHakkiHareketi.tur != HareketTuru.iptal,
                DersHakkiHareketi.id.not_in(geri_alinan),
            )
        )
    ).all()
    krediler: list[date | None] = []
    borclar: list[date] = []
    yanan = 0
    for tur, miktar, son, g in satirlar:
        if tur == HareketTuru.telafi_suresi_doldu:
            yanan -= miktar
        elif miktar > 0:
            krediler.extend([son] * miktar)
        else:
            borclar.extend([g] * -miktar)
    krediler.sort(key=_sira)
    return krediler, borclar, yanan


def _ayir(kalan: list[date | None], gunler: list[date]) -> int:
    """Her gün (eskiden yeniye) son kullanması o güne yeten en eski hakkı `kalan`dan düşer.
    Karşılığı bulunamayan gün sayısını döner. `kalan` sıralı olmalı, yerinde değişir."""
    karsiliksiz = 0
    for g in sorted(gunler):
        i = next((i for i, k in enumerate(kalan) if k is None or k >= g), None)
        if i is None:
            karsiliksiz += 1
        else:
            kalan.pop(i)
    return karsiliksiz


def _bekleyen_plan_kosullari(ogrenci_id: uuid.UUID) -> list:
    """İptal edilmemiş ve öğrencinin yoklaması henüz alınmamış telafi planları. Ek ders planları hak ayırmaz."""
    return [
        TelafiPlani.ogrenci_id == ogrenci_id,
        TelafiPlani.tur == KatilimTuru.telafi,
        DersOturumu.durum != OturumDurum.iptal,
        ~exists().where(Yoklama.oturum_id == DersOturumu.id, Yoklama.ogrenci_id == ogrenci_id),
    ]


async def _plan_gunleri(session: AsyncSession, ogrenci_id: uuid.UUID, kosul) -> list[date]:
    return list(
        (
            await session.execute(
                select(DersOturumu.tarih)
                .select_from(TelafiPlani)
                .join(DersOturumu, DersOturumu.id == TelafiPlani.oturum_id)
                .where(*_bekleyen_plan_kosullari(ogrenci_id), kosul)
            )
        ).scalars()
    )


async def kullanilabilir_telafi(
    session: AsyncSession, ogrenci_id: uuid.UUID, tarih: date | None = None, haric_oturum_id: uuid.UUID | None = None
) -> int:
    """`tarih` (varsayılan bugün) günlü bir derse planlanabilecek telafi sayısı.

    Eksiler kendi günlerinde geçerli en eski haktan düşülür; süresi dolmuş haklar kullanılamaz. İleri tarihli
    (bugün dahil) bekleyen planlar da aynı kuralla hak ayırır. Kalanlardan son kullanması `tarih`e yetenler sayılır.
    Karşılığı olmayan eksiler ve planlar sonuçtan düşülür (negatif olabilir).
    `haric_oturum_id`: bu oturumdaki plan yokmuş gibi hesaplanır (taşıma adayları; veritabanına yazılmaz)."""
    bugun_ = bugun()
    hedef = max(tarih or bugun_, bugun_)
    kalan, borclar, _ = await _telafi_satirlari(session, ogrenci_id)
    acik = _ayir(kalan, borclar)
    kalan = [k for k in kalan if k is None or k >= bugun_]
    kosul = DersOturumu.tarih >= bugun_
    if haric_oturum_id is not None:
        kosul = and_(kosul, DersOturumu.id != haric_oturum_id)
    karsiliksiz = _ayir(kalan, await _plan_gunleri(session, ogrenci_id, kosul))
    return sum(1 for k in kalan if k is None or k >= hedef) - karsiliksiz - acik


async def telafi_son_kullanma(session: AsyncSession, ogrenci_id: uuid.UUID) -> date | None:
    """Planlanabilir telafi haklarından en erken bitenin son kullanma günü (hak yoksa ya da süresizse None)."""
    bugun_ = bugun()
    kalan, borclar, _ = await _telafi_satirlari(session, ogrenci_id)
    _ayir(kalan, borclar)
    kalan = [k for k in kalan if k is None or k >= bugun_]
    _ayir(kalan, await _plan_gunleri(session, ogrenci_id, DersOturumu.tarih >= bugun_))
    return kalan[0] if kalan else None


async def telafi_uzlastir(session: AsyncSession, ogrenci_id: uuid.UUID, bugun_: date) -> int:
    """Öğrencinin süre dolumunu defterin güncel hâliyle uzlaştırır ve farkı tek satırla yazar.

    Olması gereken yanan = eksiler ve yoklaması alınmamış geçmiş telafi planları (kendi günlerinde geçerli en eski
    haktan) düşüldükten sonra son kullanması `bugun_`den önce kalan haklar. Yazılmış olandan fazlaysa eksi,
    azsa (ör. yanmış bir hakkın devamsızlığı sonradan geri alındıysa) artı `telafi_suresi_doldu` yazılır.
    Öğrenci satırı kilitlenir: iki işçi ya da işçi ile yoklama aynı anda çalışsa da fark iki kez yazılmaz.
    Dönen: yazılan net yanma (artı = hak düştü, eksi = geri verildi, 0 = değişiklik yok)."""
    await session.execute(select(Ogrenci.id).where(Ogrenci.id == ogrenci_id).with_for_update())
    kalan, borclar, yanan = await _telafi_satirlari(session, ogrenci_id)
    ayrilan = await _plan_gunleri(session, ogrenci_id, DersOturumu.tarih < bugun_)
    _ayir(kalan, borclar + ayrilan)
    olmasi_gereken = sum(1 for k in kalan if k is not None and k < bugun_)
    fark = olmasi_gereken - yanan
    if fark:
        session.add(
            DersHakkiHareketi(
                ogrenci_id=ogrenci_id,
                sayac=Sayac.telafi,
                miktar=-fark,
                tur=HareketTuru.telafi_suresi_doldu,
                neden="Telafi hakkının süresi doldu" if fark > 0 else "Süre dolumu düzeltildi (yoklama düzeltmesi)",
            )
        )
        await session.flush()
    return fark


SON_DUZELTME_PENCERESI = timedelta(days=2)


async def suresi_dolum_adaylari(session: AsyncSession, bugun_: date, simdi: datetime) -> list[uuid.UUID]:
    """Günlük işte süre dolumu değişebilecek öğrenciler (kimlik sırasıyla):
    - telafi bakiyesi artı olup son kullanması geçmiş hakkı olanlar (yanacak hak kalmış olabilir),
    - son 2 günde telafi hareketi olanlar (düzeltmeler satır içinde uzlaştırılır, bu yalnız güvenlik ağıdır).
    Hakları tamamen yanmış ve bakiyesi sıfırlanmış öğrenci aday olmaktan çıkar."""
    arti_bakiye = (
        select(DersHakkiHareketi.ogrenci_id)
        .where(DersHakkiHareketi.sayac == Sayac.telafi)
        .group_by(DersHakkiHareketi.ogrenci_id)
        .having(func.sum(DersHakkiHareketi.miktar) > 0)
    )
    suresi_gecmis = select(DersHakkiHareketi.ogrenci_id).where(
        DersHakkiHareketi.sayac == Sayac.telafi,
        DersHakkiHareketi.miktar > 0,
        DersHakkiHareketi.son_kullanma < bugun_,
        DersHakkiHareketi.ogrenci_id.in_(arti_bakiye),
    )
    yeni = select(DersHakkiHareketi.ogrenci_id).where(
        DersHakkiHareketi.sayac == Sayac.telafi,
        DersHakkiHareketi.zaman >= simdi - SON_DUZELTME_PENCERESI,
    )
    birlesik = suresi_gecmis.union(yeni).subquery()
    return list((await session.execute(select(birlesik.c.ogrenci_id).order_by(birlesik.c.ogrenci_id))).scalars())


async def suresi_dolan_telafileri_isle(
    oturum_ac: Callable[[], AsyncSession], bugun_: date, simdi: datetime | None = None
) -> int:
    """Günlük iş: adayları öğrenci başına ayrı kısa işlemde (kilit, uzlaştır, commit) uzlaştırır.
    Bir öğrencideki hata günlüğe yazılır, diğerleri devam eder. Tekrar ya da iki işçiyle çalışması güvenlidir.
    Dönen: yazılan net yanma toplamı."""
    async with oturum_ac() as session:
        adaylar = await suresi_dolum_adaylari(session, bugun_, simdi or datetime.now(timezone.utc))
    toplam = 0
    for ogrenci_id in adaylar:
        try:
            async with oturum_ac() as session:
                fark = await telafi_uzlastir(session, ogrenci_id, bugun_)
                await session.commit()
            toplam += fark
        except Exception:
            # Kişisel veri yazılmaz; öğrenci kimliği iç anahtardır.
            log.exception("Telafi süre dolumu uzlaştırılamadı (öğrenci %s)", ogrenci_id)
    return toplam


def _hareket(
    yoklama: Yoklama, sayac: Sayac, miktar: int, tur: HareketTuru, son_kullanma: date | None = None
) -> DersHakkiHareketi:
    return DersHakkiHareketi(
        son_kullanma=son_kullanma,
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
    if yoklama.ek_ders_mi:
        # Ek ders ücretsizdir: ne gelince ders düşer ne gelmeyince telafi doğar.
        yoklama.hareket_planli_zaman = None
        yoklama.hareket_islendi = True
        return
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
    sebep: DevamsizlikSebebi | None = None,
    aciklama: str | None = None,
    ek_ders_mi: bool = False,
) -> Yoklama:
    """İlk kez yoklama alınan öğrenci için kayıt ve (varsa) hareket oluşturur.
    Sebep ve açıklama yalnız gelmedi için saklanır (zorunluluk uç noktada denetlenir)."""
    gelmedi = durum == YoklamaDurum.gelmedi
    yoklama = Yoklama(
        id=uuid.uuid4(),
        oturum_id=oturum_id,
        ogrenci_id=ogrenci_id,
        durum=durum,
        sebep=sebep if gelmedi else None,
        aciklama=aciklama if gelmedi else None,
        telafi_mi=telafi_mi,
        ek_ders_mi=ek_ders_mi,
        isaretleyen_id=isaretleyen_id,
        zaman=simdi,
        surum=0,
        hareket_islendi=False,
    )
    session.add(yoklama)
    await session.flush()
    _durumun_etkisi(session, yoklama, simdi)
    await session.flush()
    await telafi_uzlastir(session, ogrenci_id, bugun(simdi))
    await bildirim.yoklama_isaretlendi(session, yoklama, simdi)
    return yoklama


async def yoklama_uygula(
    session: AsyncSession,
    yoklama: Yoklama,
    yeni_durum: YoklamaDurum,
    isaretleyen_id: uuid.UUID | None,
    simdi: datetime,
    sebep: DevamsizlikSebebi | None = None,
    aciklama: str | None = None,
) -> None:
    """Var olan yoklamanın durumunu ya da devamsızlık sebebini değiştirir. Eski hareketler iptal edilir, sürüm artar.
    Yalnız açıklama değişirse sürüm artmaz, deftere dokunulmaz."""
    gelmedi = yeni_durum == YoklamaDurum.gelmedi
    yeni_sebep = sebep if gelmedi else None
    yoklama.aciklama = aciklama if gelmedi else None
    if yoklama.durum == yeni_durum and yoklama.sebep == yeni_sebep:
        return
    yoklama.isaretleyen_id = isaretleyen_id
    await _acik_hareketleri_iptal_et(session, yoklama)
    # Eski durum gelmedi ise bekleyen devamsızlık bildirimi geri alınır (gönderilmiş olana dokunulmaz).
    if yoklama.durum == YoklamaDurum.gelmedi:
        await bildirim.gelmedi_iptal_et(session, yoklama.id)
    yoklama.surum += 1
    yoklama.durum = yeni_durum
    yoklama.sebep = yeni_sebep
    yoklama.zaman = simdi
    _durumun_etkisi(session, yoklama, simdi)
    await session.flush()
    # Geri alınan devamsızlık telafisi daha önce yanmış olabilir: süre dolumu hemen uzlaştırılır.
    await telafi_uzlastir(session, yoklama.ogrenci_id, bugun(simdi))
    await bildirim.yoklama_isaretlendi(session, yoklama, simdi)


async def bekleyen_devamsizliklari_isle(session: AsyncSession, simdi: datetime) -> int:
    """Planlı zamanı gelmiş `gelmedi` yoklamalarının devamsızlık hareketini yazar.
    Birden çok işçi çalışsa da aynı yoklama iki kez işlenmez. Dönen sayı: hareket yazılan yoklama sayısı."""
    bekleyenler = (
        await session.execute(
            select(Yoklama, DersOturumu.tarih)
            .join(DersOturumu, DersOturumu.id == Yoklama.oturum_id)
            .where(
                Yoklama.hareket_islendi.is_(False),
                Yoklama.hareket_planli_zaman.is_not(None),
                Yoklama.hareket_planli_zaman <= simdi,
            )
            .order_by(Yoklama.hareket_planli_zaman)
            .with_for_update(of=Yoklama, skip_locked=True)
        )
    ).all()
    # Öğrenci satırları kimlik sırasıyla kilitlenir (yoklama uç noktası ve süre dolumu ile aynı sıra).
    ogrenciler = sorted({y.ogrenci_id for y, _ in bekleyenler})
    if ogrenciler:
        await session.execute(
            select(Ogrenci.id).where(Ogrenci.id.in_(ogrenciler)).order_by(Ogrenci.id).with_for_update()
        )
    yazilan = 0
    hakki_dusenler = []
    for y, ders_tarihi in bekleyenler:
        # Süre içinde düzeltildiyse (artık gelmedi değilse) hak doğmaz.
        if y.durum == YoklamaDurum.gelmedi and not y.telafi_mi and not y.ek_ders_mi:
            session.add(_hareket(y, Sayac.normal, -1, HareketTuru.devamsizlik))
            # Habersiz devamsızlıkta ders yanar, telafi doğmaz. Sebebi olmayan eski kayıtlar mazeretli sayılır.
            if y.sebep is None or y.sebep in MAZERETLI_SEBEPLER:
                session.add(_hareket(y, Sayac.telafi, 1, HareketTuru.devamsizlik, ay_sonu(ders_tarihi)))
            yazilan += 1
            hakki_dusenler.append(y)
        y.hareket_islendi = True
    await session.flush()
    for y in hakki_dusenler:
        # Ay sonunu geçmiş dersin hakkı doğar doğmaz yanar (ör. 31'inde 23:30 dersi).
        await telafi_uzlastir(session, y.ogrenci_id, bugun(simdi))
        await bildirim.bakiye_olaylari(session, y.ogrenci_id, y.id, simdi)
    return yazilan
