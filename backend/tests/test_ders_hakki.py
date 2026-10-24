"""Ders hakkı servisi: saat enjekte edilir, gerçek bekleme yoktur."""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select

from app import ders_hakki
from app.db import SessionLocal
from app.models import (
    DersHakkiHareketi,
    DersOturumu,
    Grup,
    HareketTuru,
    Ogrenci,
    Yoklama,
    YoklamaDurum,
)

T0 = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
SAAT = timedelta(hours=1)


async def ortam():
    async with SessionLocal() as s:
        g = Grup(ad="A", kontenjan=10)
        o = Ogrenci(ad="Deneme", soyad="Öğrenci", dogum_tarihi=date(2016, 1, 3))
        s.add_all([g, o])
        await s.flush()
        ot = DersOturumu(grup_id=g.id, tarih=date(2026, 11, 2), baslangic=time(17), bitis=time(18, 30))
        s.add(ot)
        await s.commit()
        return o.id, ot.id


async def isaretle(ogrenci_id, oturum_id, durum, an, telafi_mi=False):
    """İlk işaretleme ya da düzeltme (api'nin yaptığı gibi)."""
    async with SessionLocal() as s:
        y = (
            await s.execute(select(Yoklama).where(Yoklama.oturum_id == oturum_id, Yoklama.ogrenci_id == ogrenci_id))
        ).scalar_one_or_none()
        if y is None:
            await ders_hakki.yoklama_olustur(
                s, oturum_id=oturum_id, ogrenci_id=ogrenci_id, durum=durum, telafi_mi=telafi_mi,
                isaretleyen_id=None, simdi=an,
            )
        else:
            await ders_hakki.yoklama_uygula(s, y, durum, None, an)
        await s.commit()


async def isle(an) -> int:
    async with SessionLocal() as s:
        sayi = await ders_hakki.bekleyen_devamsizliklari_isle(s, an)
        await s.commit()
        return sayi


async def bakiye(ogrenci_id):
    async with SessionLocal() as s:
        return await ders_hakki.bakiye(s, ogrenci_id)


async def hareketler():
    async with SessionLocal() as s:
        return list((await s.execute(select(DersHakkiHareketi).order_by(DersHakkiHareketi.id))).scalars())


def turler(satirlar):
    return [(h.tur.value, h.sayac.value, h.miktar) for h in satirlar]


async def test_bos_ogrencinin_bakiyesi_sifir():
    o, _ = await ortam()
    assert await bakiye(o) == {"normal": 0, "telafi": 0}


async def test_geldi_hemen_normal_eksi_bir_yazar():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.geldi, T0)
    assert await bakiye(o) == {"normal": -1, "telafi": 0}  # paket yoksa negatife düşebilir
    h = await hareketler()
    assert turler(h) == [("ders_kullanimi", "normal", -1)]
    assert h[0].yoklama_surum == 0


async def test_ayni_durum_tekrar_gonderilirse_hicbir_sey_yazilmaz():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.geldi, T0)
    await isaretle(o, ot, YoklamaDurum.geldi, T0 + SAAT)
    assert len(await hareketler()) == 1
    async with SessionLocal() as s:
        assert (await s.execute(select(Yoklama.surum))).scalar_one() == 0


async def test_gelmedi_bir_saat_dolmadan_hareket_yazmaz_sonra_devamsizlik_dogar():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0)
    assert await hareketler() == []
    assert await isle(T0 + timedelta(minutes=59)) == 0
    assert await hareketler() == []
    assert await isle(T0 + timedelta(minutes=61)) == 1
    assert await bakiye(o) == {"normal": -1, "telafi": 1}
    h = await hareketler()
    assert sorted(turler(h)) == [("devamsizlik", "normal", -1), ("devamsizlik", "telafi", 1)]


async def test_isci_iki_kez_calisinca_tek_hareket_yazar():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0)
    assert await isle(T0 + timedelta(minutes=61)) == 1
    assert await isle(T0 + timedelta(minutes=62)) == 0
    assert len(await hareketler()) == 2
    assert await bakiye(o) == {"normal": -1, "telafi": 1}


async def test_bir_saat_icinde_duzeltilirse_devamsizlik_hic_dogmaz():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0)
    await isaretle(o, ot, YoklamaDurum.geldi, T0 + timedelta(minutes=20))
    assert await isle(T0 + timedelta(hours=3)) == 0
    assert turler(await hareketler()) == [("ders_kullanimi", "normal", -1)]
    assert await bakiye(o) == {"normal": -1, "telafi": 0}


async def test_isleme_aninda_durum_degismisse_hareket_yazilmaz():
    """Düzeltme ile işçi arasındaki yarışta: planlı zaman geçmiş ama durum artık geldi."""
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0)
    async with SessionLocal() as s:
        y = (await s.execute(select(Yoklama))).scalar_one()
        y.durum = YoklamaDurum.geldi  # hareket planı hâlâ açık kalmış gibi
        await s.commit()
    assert await isle(T0 + SAAT) == 0
    assert await hareketler() == []
    async with SessionLocal() as s:
        assert (await s.execute(select(Yoklama.hareket_islendi))).scalar_one() is True


async def test_islendikten_sonra_duzeltme_devamsizligi_iptal_eder():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0)
    await isle(T0 + timedelta(minutes=61))
    await isaretle(o, ot, YoklamaDurum.geldi, T0 + timedelta(hours=2))
    assert await bakiye(o) == {"normal": -1, "telafi": 0}
    h = await hareketler()
    assert sorted(turler(h)) == sorted(
        [
            ("devamsizlik", "normal", -1),
            ("devamsizlik", "telafi", 1),
            ("iptal", "normal", 1),
            ("iptal", "telafi", -1),
            ("ders_kullanimi", "normal", -1),
        ]
    )
    # İptal satırları geri aldıkları hareketi gösterir, yoklama sürümü boştur.
    iptaller = [x for x in h if x.tur == HareketTuru.iptal]
    assert all(x.iptal_edilen_id is not None and x.yoklama_id is None and x.yoklama_surum is None for x in iptaller)
    assert next(x for x in h if x.tur == HareketTuru.ders_kullanimi).yoklama_surum == 1


async def test_geldi_gelmedi_geldi_gelmedi_zincirinde_bakiye_dogru_ve_kisit_patlamaz():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.geldi, T0)
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0 + timedelta(minutes=5))
    assert await bakiye(o) == {"normal": 0, "telafi": 0}  # ders_kullanimi geri alındı, devamsızlık henüz yok
    await isle(T0 + timedelta(hours=2))
    assert await bakiye(o) == {"normal": -1, "telafi": 1}
    await isaretle(o, ot, YoklamaDurum.geldi, T0 + timedelta(hours=3))
    assert await bakiye(o) == {"normal": -1, "telafi": 0}
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0 + timedelta(hours=4))
    assert await bakiye(o) == {"normal": 0, "telafi": 0}
    assert await isle(T0 + timedelta(hours=4, minutes=30)) == 0
    assert await isle(T0 + timedelta(hours=5, minutes=1)) == 1
    assert await bakiye(o) == {"normal": -1, "telafi": 1}
    async with SessionLocal() as s:
        assert (await s.execute(select(Yoklama.surum))).scalar_one() == 3


async def test_telafi_dersine_geldi_telafi_eksi_bir():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.geldi, T0, telafi_mi=True)
    assert await bakiye(o) == {"normal": 0, "telafi": -1}
    assert turler(await hareketler()) == [("telafi_kullanimi", "telafi", -1)]


async def test_telafi_dersine_gelmedi_hicbir_hareket_yok():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0, telafi_mi=True)
    assert await isle(T0 + timedelta(hours=5)) == 0
    assert await hareketler() == []
    async with SessionLocal() as s:
        y = (await s.execute(select(Yoklama))).scalar_one()
        assert y.hareket_islendi is True and y.hareket_planli_zaman is None


async def test_telafi_gelmedi_sonra_geldi_sonra_gelmedi_geri_alir():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.geldi, T0, telafi_mi=True)
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0 + timedelta(minutes=10))
    assert await bakiye(o) == {"normal": 0, "telafi": 0}
    assert await isle(T0 + timedelta(hours=3)) == 0


async def test_defter_satirlari_degismez_yalnizca_yeni_satir_eklenir():
    o, ot = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0)
    await isle(T0 + timedelta(minutes=61))
    once = [(h.id, h.sayac, h.miktar, h.tur, h.yoklama_id, h.yoklama_surum, h.iptal_edilen_id) for h in await hareketler()]
    await isaretle(o, ot, YoklamaDurum.geldi, T0 + timedelta(hours=2))
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0 + timedelta(hours=3))
    sonra = [(h.id, h.sayac, h.miktar, h.tur, h.yoklama_id, h.yoklama_surum, h.iptal_edilen_id) for h in await hareketler()]
    assert sonra[: len(once)] == once
    assert len(sonra) > len(once)


async def test_birden_cok_ogrenci_bakiyesi_tek_cagrida():
    o1, ot = await ortam()
    async with SessionLocal() as s:
        o2 = Ogrenci(ad="Ikinci", soyad="Kisi", dogum_tarihi=date(2016, 1, 3))
        s.add(o2)
        await s.commit()
    await isaretle(o1, ot, YoklamaDurum.geldi, T0)
    async with SessionLocal() as s:
        sonuc = await ders_hakki.bakiyeler(s, [o1, o2.id])
    assert sonuc == {o1: {"normal": -1, "telafi": 0}, o2.id: {"normal": 0, "telafi": 0}}
