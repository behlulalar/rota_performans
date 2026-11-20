"""Devamsızlık sebebi ve aylık telafi süresi: defter kuralları, süre dolumu, planlama, gizlilik, bildirim, devam özeti."""
import asyncio
from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select

from app import bildirim as bsvc
from app import ders_hakki
from app.db import SessionLocal
from app.models import (
    Bildirim,
    BildirimDurum,
    DersHakkiHareketi,
    DersOturumu,
    DevamsizlikSebebi,
    Grup,
    HareketTuru,
    IletisimKisisi,
    IletisimRolu,
    Ogrenci,
    OturumDurum,
    Sayac,
    TelafiPlani,
    Yoklama,
    YoklamaDurum,
)
from tests.test_sema import ihlal
from tests.test_telafi import planla
from tests.test_veli_paneli import baslik, veli_ve_cocuk
from tests.test_yoklama import (  # noqa: F401  (yonetici fixture)
    BUGUN,
    antrenor_hesabi,
    govde,
    grup_olustur,
    kaydet,
    ogrenci_olustur,
    oturum_olustur,
    uye_yap,
    yonetici,
)

SAAT = timedelta(hours=1)
S = DevamsizlikSebebi


# ---------- yardımcılar (servis düzeyi, saat enjekte) ----------


async def ortam(tarih=date(2026, 11, 2), baslangic=time(17)):
    async with SessionLocal() as s:
        g = Grup(ad="A", kontenjan=10)
        o = Ogrenci(ad="Deniz", soyad="Öğrenci", dogum_tarihi=date(2016, 1, 3))
        s.add_all([g, o])
        await s.flush()
        ot = DersOturumu(grup_id=g.id, tarih=tarih, baslangic=baslangic, bitis=time(baslangic.hour, 59))
        s.add(ot)
        await s.commit()
        return o.id, ot.id, g.id


async def oturum_ekle(grup_id, tarih):
    async with SessionLocal() as s:
        ot = DersOturumu(grup_id=grup_id, tarih=tarih, baslangic=time(17), bitis=time(18))
        s.add(ot)
        await s.commit()
        return ot.id


async def isaretle(ogrenci_id, oturum_id, durum, an, sebep=None, aciklama=None, telafi_mi=False):
    async with SessionLocal() as s:
        y = (
            await s.execute(select(Yoklama).where(Yoklama.oturum_id == oturum_id, Yoklama.ogrenci_id == ogrenci_id))
        ).scalar_one_or_none()
        if y is None:
            await ders_hakki.yoklama_olustur(
                s, oturum_id=oturum_id, ogrenci_id=ogrenci_id, durum=durum, telafi_mi=telafi_mi,
                isaretleyen_id=None, simdi=an, sebep=sebep, aciklama=aciklama,
            )
        else:
            await ders_hakki.yoklama_uygula(s, y, durum, None, an, sebep=sebep, aciklama=aciklama)
        await s.commit()


async def isle(an):
    async with SessionLocal() as s:
        sayi = await ders_hakki.bekleyen_devamsizliklari_isle(s, an)
        await s.commit()
        return sayi


async def sure_doldur(gun):
    return await ders_hakki.suresi_dolan_telafileri_isle(SessionLocal, gun)


async def bakiye(ogrenci_id):
    async with SessionLocal() as s:
        return await ders_hakki.bakiye(s, ogrenci_id)


async def hareketler(ogrenci_id=None):
    async with SessionLocal() as s:
        q = select(DersHakkiHareketi).order_by(DersHakkiHareketi.id)
        if ogrenci_id is not None:
            q = q.where(DersHakkiHareketi.ogrenci_id == ogrenci_id)
        return list((await s.execute(q)).scalars())


def ozet(satirlar):
    return [(h.tur.value, h.sayac.value, h.miktar) for h in satirlar]


async def kredi(ogrenci_id, son_kullanma, miktar=1):
    """Telafi hakkı (elle düzeltme satırı, istenen son kullanmayla)."""
    await kaydet(DersHakkiHareketi(
        ogrenci_id=ogrenci_id, sayac=Sayac.telafi, miktar=miktar, tur=HareketTuru.manuel_duzeltme,
        neden="Test hakkı", son_kullanma=son_kullanma,
    ))


async def kullanim(ogrenci_id, zaman, miktar=-1):
    await kaydet(DersHakkiHareketi(
        ogrenci_id=ogrenci_id, sayac=Sayac.telafi, miktar=miktar, tur=HareketTuru.manuel_duzeltme, neden="Test kullanım",
        zaman=zaman,
    ))


def t(gun, saat=18, ay=11, yil=2026):
    return datetime(yil, ay, gun, saat, 0, tzinfo=timezone.utc)


# ---------- defter kuralları ----------


def test_ay_sonu():
    assert ders_hakki.ay_sonu(date(2026, 11, 2)) == date(2026, 11, 30)
    assert ders_hakki.ay_sonu(date(2026, 12, 31)) == date(2026, 12, 31)
    assert ders_hakki.ay_sonu(date(2028, 2, 10)) == date(2028, 2, 29)
    assert ders_hakki.ay_sonu(date(2027, 2, 1)) == date(2027, 2, 28)


@pytest.mark.parametrize("sebep", [S.izinli, S.raporlu, S.yarisma])
async def test_mazeretli_gelmedi_telafi_dogar_ay_sonuna_kadar(sebep):
    o, ot, _ = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2), sebep)
    assert await isle(t(2) + SAAT) == 1
    h = await hareketler()
    assert ozet(h) == [("devamsizlik", "normal", -1), ("devamsizlik", "telafi", 1)]
    assert h[0].son_kullanma is None and h[1].son_kullanma == date(2026, 11, 30)
    assert await bakiye(o) == {"normal": -1, "telafi": 1}


async def test_habersiz_devamsizlikta_ders_yanar_telafi_dogmaz():
    o, ot, _ = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2), S.devamsiz, "Haber vermedi")
    assert await isle(t(2) + SAAT) == 1
    assert ozet(await hareketler()) == [("devamsizlik", "normal", -1)]
    assert await bakiye(o) == {"normal": -1, "telafi": 0}
    async with SessionLocal() as s:
        y = (await s.execute(select(Yoklama))).scalar_one()
    assert (y.sebep, y.aciklama) == (S.devamsiz, "Haber vermedi")


async def test_sebepsiz_eski_kayit_mazeretli_sayilir():
    o, ot, _ = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2))
    await isle(t(2) + SAAT)
    h = await hareketler()
    assert ozet(h) == [("devamsizlik", "normal", -1), ("devamsizlik", "telafi", 1)]
    assert h[1].son_kullanma == date(2026, 11, 30)


async def test_ay_sonu_istanbul_saatiyle_dersin_tarihine_gore():
    # 31 Ekim 23:00 (İstanbul) dersi, hak 1 Kasım 00:30 İstanbul'da (31 Ekim 21:30 UTC) doğar: yine Ekim'e aittir.
    o, ot, _ = await ortam(tarih=date(2026, 10, 31), baslangic=time(23))
    isaret = datetime(2026, 10, 31, 20, 30, tzinfo=timezone.utc)  # 23:30 İstanbul
    await isaretle(o, ot, YoklamaDurum.gelmedi, isaret, S.raporlu)
    await isle(isaret + SAAT)
    telafi_ = [h for h in await hareketler() if h.sayac == Sayac.telafi]
    assert telafi_[0].son_kullanma == date(2026, 10, 31)
    # Hak 1 Kasım'da (İstanbul) doğduğu için doğar doğmaz yanar; günlük iş yeni bir şey yazmaz.
    assert [(h.tur, h.miktar) for h in telafi_[1:]] == [(HareketTuru.telafi_suresi_doldu, -1)]
    assert await sure_doldur(date(2026, 11, 1)) == 0
    assert await bakiye(o) == {"normal": -1, "telafi": 0}
    # 30 Kasım dersi: son gün 30 Kasım.
    _, ot2, _ = await ortam(tarih=date(2026, 11, 30))
    async with SessionLocal() as s:
        oid2 = (await s.execute(select(Ogrenci.id).where(Ogrenci.id != o))).scalars().first()
    await isaretle(oid2, ot2, YoklamaDurum.gelmedi, t(30), S.izinli)
    await isle(t(30) + SAAT)
    assert [h.son_kullanma for h in await hareketler(oid2) if h.sayac == Sayac.telafi] == [date(2026, 11, 30)]


async def test_telafi_dersinde_gelmedi_sebep_saklanir_defter_degismez():
    o, ot, _ = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2), S.raporlu, telafi_mi=True)
    assert await isle(t(2) + SAAT) == 0
    assert await hareketler() == []
    async with SessionLocal() as s:
        assert (await s.execute(select(Yoklama.sebep))).scalar_one() == S.raporlu


async def test_sebep_suresinde_degisirse_yalniz_son_sebebin_etkisi():
    o, ot, _ = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2), S.izinli)
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2) + timedelta(minutes=20), S.devamsiz)
    async with SessionLocal() as s:
        assert (await s.execute(select(Yoklama.surum))).scalar_one() == 1
    assert await isle(t(2) + SAAT) == 0  # yeni sürümün bekleme süresi dolmadı
    assert await isle(t(2) + timedelta(minutes=80)) == 1
    assert ozet(await hareketler()) == [("devamsizlik", "normal", -1)]


async def test_is_calistiktan_sonra_izinliden_devamsiza_net_dogru():
    o, ot, _ = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2), S.izinli)
    await isle(t(2) + SAAT)
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2) + 2 * SAAT, S.devamsiz)
    await isle(t(2) + 3 * SAAT)
    assert await bakiye(o) == {"normal": -1, "telafi": 0}
    assert ozet(await hareketler()) == [
        ("devamsizlik", "normal", -1), ("devamsizlik", "telafi", 1),
        ("iptal", "normal", 1), ("iptal", "telafi", -1),
        ("devamsizlik", "normal", -1),
    ]
    # Geri: devamsızdan raporluya.
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2) + 4 * SAAT, S.raporlu)
    await isle(t(2) + 5 * SAAT)
    assert await bakiye(o) == {"normal": -1, "telafi": 1}


async def test_yalniz_aciklama_degisirse_surum_artmaz():
    o, ot, _ = await ortam()
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2), S.izinli, "ilk")
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2) + timedelta(minutes=5), S.izinli, "ikinci")
    async with SessionLocal() as s:
        y = (await s.execute(select(Yoklama))).scalar_one()
    assert (y.surum, y.aciklama) == (0, "ikinci")
    # Geldi'ye dönünce sebep ve açıklama temizlenir.
    await isaretle(o, ot, YoklamaDurum.geldi, t(2) + timedelta(minutes=6), S.izinli, "x")
    async with SessionLocal() as s:
        y = (await s.execute(select(Yoklama))).scalar_one()
    assert (y.durum, y.sebep, y.aciklama) == (YoklamaDurum.geldi, None, None)


async def test_veritabani_sebebi_yalniz_gelmedide_kabul_eder():
    o, ot, _ = await ortam()
    await ihlal("ck_yoklama_sebep_yalniz_gelmedi", Yoklama(oturum_id=ot, ogrenci_id=o, durum=YoklamaDurum.geldi, sebep=S.izinli))
    await ihlal("ck_yoklama_aciklama_uzunlugu", Yoklama(oturum_id=ot, ogrenci_id=o, durum=YoklamaDurum.gelmedi, aciklama="x" * 501))


# ---------- süre dolumu ----------


async def test_sure_dolumu_tekrar_calisinca_yeni_hareket_yazmaz():
    o, _, _ = await ortam()
    await kredi(o, date(2026, 10, 31), 2)
    await kredi(o, date(2026, 11, 30))
    await kredi(o, None)  # süresiz (elle verilen)
    assert await sure_doldur(date(2026, 11, 1)) == 2
    assert await sure_doldur(date(2026, 11, 1)) == 0
    assert await sure_doldur(date(2026, 11, 15)) == 0
    assert await bakiye(o) == {"normal": 0, "telafi": 2}
    assert await sure_doldur(date(2026, 12, 1)) == 1
    assert await sure_doldur(date(2027, 6, 1)) == 0  # süresiz hak yanmaz
    yanan = [h for h in await hareketler() if h.tur == HareketTuru.telafi_suresi_doldu]
    assert [h.miktar for h in yanan] == [-2, -1]
    assert await bakiye(o) == {"normal": 0, "telafi": 1}


async def test_sure_dolumu_bir_ogrencideki_hata_digerlerini_durdurmaz(monkeypatch):
    o1, _, _ = await ortam()
    o2, _, _ = await ortam()
    await kredi(o1, date(2026, 10, 31))
    await kredi(o2, date(2026, 10, 31))
    asil = ders_hakki.telafi_uzlastir
    bozuk = min(o1, o2)

    async def sahte(session, ogrenci_id, gun):
        if ogrenci_id == bozuk:
            raise RuntimeError("deneme")
        return await asil(session, ogrenci_id, gun)

    monkeypatch.setattr(ders_hakki, "telafi_uzlastir", sahte)
    assert await sure_doldur(date(2026, 11, 1)) == 1
    assert (await bakiye(bozuk))["telafi"] == 1 and (await bakiye(max(o1, o2)))["telafi"] == 0


async def test_sure_dolumu_adaylari_daralir():
    o, _, _ = await ortam()
    await kredi(o, date(2026, 10, 31))
    gelecek = datetime(2027, 1, 1, tzinfo=timezone.utc)  # son hareketler 2 günlük pencerenin dışında
    async with SessionLocal() as s:
        assert await ders_hakki.suresi_dolum_adaylari(s, date(2026, 11, 1), gelecek) == [o]
    assert await sure_doldur(date(2026, 11, 1)) == 1
    async with SessionLocal() as s:
        assert await ders_hakki.suresi_dolum_adaylari(s, date(2026, 11, 2), gelecek) == []


async def test_sure_dolumu_iki_isci_ayni_anda_tek_hareket():
    o, _, _ = await ortam()
    await kredi(o, date(2026, 10, 31), 3)
    sonuc = await asyncio.gather(sure_doldur(date(2026, 11, 1)), sure_doldur(date(2026, 11, 1)))
    assert sorted(sonuc) == [0, 3]
    assert await bakiye(o) == {"normal": 0, "telafi": 0}


async def test_en_eski_hak_once_tuketilir_aylar_arasi():
    o, _, _ = await ortam()
    await kredi(o, date(2026, 10, 31))
    await kredi(o, date(2026, 11, 30))
    await kullanim(o, t(20, ay=10))  # Ekim'de: Ekim hakkını tüketir
    assert await sure_doldur(date(2026, 11, 1)) == 0
    assert await bakiye(o) == {"normal": 0, "telafi": 1}
    assert await sure_doldur(date(2026, 12, 1)) == 1
    assert await bakiye(o) == {"normal": 0, "telafi": 0}


async def test_suresi_dolmus_hakki_sonraki_kullanim_tuketemez():
    o, _, _ = await ortam()
    await kredi(o, date(2026, 10, 31))
    await kredi(o, date(2026, 11, 30))
    await kullanim(o, t(10))  # Kasım'da: Ekim hakkı geçersiz, Kasım hakkını tüketir
    assert await sure_doldur(date(2026, 11, 11)) == 1
    assert await sure_doldur(date(2026, 12, 1)) == 0
    assert await bakiye(o) == {"normal": 0, "telafi": 0}


async def test_yoklamasi_alinmamis_gecmis_telafi_plani_hakki_korur():
    o, _, g = await ortam()
    await kredi(o, date(2026, 10, 31))
    plan_ot = await oturum_ekle(g, date(2026, 10, 30))
    await kaydet(TelafiPlani(oturum_id=plan_ot, ogrenci_id=o))
    assert await sure_doldur(date(2026, 11, 1)) == 0
    # Yoklama geç alınıp gelmedi olursa hak hemen yanar.
    await isaretle(o, plan_ot, YoklamaDurum.gelmedi, t(1), S.izinli, telafi_mi=True)
    assert await bakiye(o) == {"normal": 0, "telafi": 0}
    assert await sure_doldur(date(2026, 11, 2)) == 0


async def test_gec_alinan_telafi_yoklamasi_geldi_bakiye_negatife_dusmez():
    o, _, g = await ortam()
    await kredi(o, date(2026, 10, 31))
    plan_ot = await oturum_ekle(g, date(2026, 10, 30))
    await kaydet(TelafiPlani(oturum_id=plan_ot, ogrenci_id=o))
    await sure_doldur(date(2026, 11, 1))
    await isaretle(o, plan_ot, YoklamaDurum.geldi, t(1), telafi_mi=True)
    assert await sure_doldur(date(2026, 11, 2)) == 0
    assert await bakiye(o) == {"normal": 0, "telafi": 0}


async def test_geri_alinan_kullanim_sonrasi_hak_yanar():
    o, ot, _ = await ortam(tarih=date(2026, 10, 20))
    await kredi(o, date(2026, 10, 31))
    await isaretle(o, ot, YoklamaDurum.geldi, t(20, ay=10), telafi_mi=True)
    assert await sure_doldur(date(2026, 11, 1)) == 0
    # Kasım'da telafi dersi yoklaması gelmedi olarak düzeltilir: kullanım geri alınır, Ekim hakkı yanar.
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(3), S.izinli, telafi_mi=True)
    assert await bakiye(o) == {"normal": 0, "telafi": 0}  # uzlaştırma düzeltmeyle birlikte çalıştı
    assert await sure_doldur(date(2026, 11, 3)) == 0


@pytest.mark.parametrize("duzeltme", [(YoklamaDurum.geldi, None), (YoklamaDurum.gelmedi, S.devamsiz)])
async def test_yanmis_hakkin_devamsizligi_sonradan_duzeltilirse_artik_eksi_kalmaz(duzeltme):
    o, ot, _ = await ortam(tarih=date(2026, 10, 20))
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(20, ay=10), S.izinli)
    await isle(t(20, ay=10) + SAAT)
    assert await sure_doldur(date(2026, 11, 1)) == 1
    assert await bakiye(o) == {"normal": -1, "telafi": 0}
    # Kasım'da düzeltilir: Ekim hakkı geri alınır, yanması da geri verilir (artı süre dolumu satırı).
    durum, sebep = duzeltme
    await isaretle(o, ot, durum, t(5), sebep)
    await isle(t(5) + 2 * SAAT)
    assert (await bakiye(o))["telafi"] == 0
    assert [h.miktar for h in await hareketler() if h.tur == HareketTuru.telafi_suresi_doldu] == [-1, 1]
    # Sonraki geçerli hak yenmez.
    await kredi(o, date(2026, 11, 30))
    assert await sure_doldur(date(2026, 11, 10)) == 0
    assert (await bakiye(o))["telafi"] == 1
    assert await sure_doldur(date(2026, 12, 1)) == 1
    assert (await bakiye(o))["telafi"] == 0


async def test_gecikmis_is_plani_yeni_hakla_karsilar_eski_hak_yanar():
    o, _, g = await ortam()
    await kredi(o, date(2026, 10, 31))  # A
    await kredi(o, date(2026, 11, 30))  # B
    plan_ot = await oturum_ekle(g, date(2026, 11, 5))
    await kaydet(TelafiPlani(oturum_id=plan_ot, ogrenci_id=o))
    # İş 6 Kasım'a gecikti: 5 Kasım planı A'yı (31 Ekim) ayıramaz, B'yi ayırır; A yanar.
    assert await sure_doldur(date(2026, 11, 6)) == 1
    assert await bakiye(o) == {"normal": 0, "telafi": 1}
    await isaretle(o, plan_ot, YoklamaDurum.geldi, t(6), telafi_mi=True)
    assert await bakiye(o) == {"normal": 0, "telafi": 0}
    assert await sure_doldur(date(2026, 11, 7)) == 0
    assert await sure_doldur(date(2026, 12, 1)) == 0


# ---------- kullanılabilir telafi ve planlama ----------


async def kullanilabilir(o, tarih=None):
    async with SessionLocal() as s:
        return await ders_hakki.kullanilabilir_telafi(s, o, tarih)


async def test_kullanilabilir_telafi_hedef_tarihe_gore():
    o, _, _ = await ortam()
    bu_ay = ders_hakki.ay_sonu(BUGUN)
    gelecek_ay = ders_hakki.ay_sonu(bu_ay + timedelta(days=1))
    await kredi(o, BUGUN - timedelta(days=40))  # süresi geçmiş (iş henüz çalışmamış olsa da kullanılamaz)
    await kredi(o, bu_ay)
    await kredi(o, gelecek_ay)
    assert await kullanilabilir(o) == 2
    assert await kullanilabilir(o, bu_ay) == 2
    assert await kullanilabilir(o, bu_ay + timedelta(days=1)) == 1
    assert await kullanilabilir(o, gelecek_ay + timedelta(days=1)) == 0


async def test_planlama_ay_sonundan_sonrasina_422_once_200(istemci, yonetici):
    o = await ogrenci_olustur()
    await kredi(o.id, ders_hakki.ay_sonu(BUGUN))
    g = await grup_olustur("DIGER")
    sonra = await oturum_olustur(g, ders_hakki.ay_sonu(BUGUN) + timedelta(days=1))
    simdi_ = await oturum_olustur(g, BUGUN)
    # Adaylar: ay sonundan sonraki ders listelenmez.
    aday = await istemci.get(
        f"/api/ogrenciler/{o.id}/telafi-adaylari?baslangic={BUGUN}&bitis={BUGUN + timedelta(days=30)}", headers=yonetici
    )
    idler = [c["oturum"]["id"] for c in aday.json()]
    assert str(simdi_.id) in idler and str(sonra.id) not in idler
    y = await planla(istemci, yonetici, sonra, o)
    assert y.status_code == 422 and "ayın sonuna kadar" in y.json()["detail"]
    assert (await planla(istemci, yonetici, simdi_, o)).status_code == 200
    y = await planla(istemci, yonetici, sonra, o)
    assert y.status_code == 422 and y.json()["detail"] == "Kullanılabilir telafi hakkı yok"


async def test_planlama_yeni_plan_eskisinin_hakkini_calmaz(istemci, yonetici):
    # Bu ayın hakkı bu ayki plana, gelecek ayın hakkı gelecek ayki plana yeter; tersi olmaz.
    o = await ogrenci_olustur()
    bu_ay = ders_hakki.ay_sonu(BUGUN)
    await kredi(o.id, bu_ay)
    await kredi(o.id, ders_hakki.ay_sonu(bu_ay + timedelta(days=1)))
    g = await grup_olustur("DIGER")
    sonra = await oturum_olustur(g, bu_ay + timedelta(days=1))
    simdi_ = await oturum_olustur(g, BUGUN)
    assert (await planla(istemci, yonetici, sonra, o)).status_code == 200
    assert (await planla(istemci, yonetici, simdi_, o)).status_code == 200
    assert await kullanilabilir(o.id) == 0


# ---------- uç nokta: doğrulama, okuma, veli gizliliği ----------


async def yoklama_put(istemci, baslik_, ot, satirlar):
    return await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=satirlar, headers=baslik_)


async def test_gelmedi_sebepsiz_422_geldi_sebepli_422(istemci, yonetici):
    g = await grup_olustur()
    o = await ogrenci_olustur()
    await uye_yap(o, g)
    ot = await oturum_olustur(g)
    y = await yoklama_put(istemci, yonetici, ot, [{"ogrenci_id": str(o.id), "durum": "gelmedi"}])
    assert y.status_code == 422 and "sebebi seçilmeli" in y.json()["detail"]
    y = await yoklama_put(istemci, yonetici, ot, [{"ogrenci_id": str(o.id), "durum": "geldi", "sebep": "izinli"}])
    assert y.status_code == 422 and "yalnız gelmedi" in y.json()["detail"]
    y = await yoklama_put(istemci, yonetici, ot, [{"ogrenci_id": str(o.id), "durum": "geldi", "aciklama": "not"}])
    assert y.status_code == 422
    y = await yoklama_put(istemci, yonetici, ot, [{"ogrenci_id": str(o.id), "durum": "gelmedi", "sebep": "hasta"}])
    assert y.status_code == 422
    y = await yoklama_put(
        istemci, yonetici, ot, [{"ogrenci_id": str(o.id), "durum": "gelmedi", "sebep": "izinli", "aciklama": "x" * 501}]
    )
    assert y.status_code == 422
    async with SessionLocal() as s:
        assert (await s.execute(select(Yoklama))).first() is None


async def test_antrenor_ve_yonetici_sebep_ve_aciklamayi_gorur(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "hoca@kulup.com", "Hoca")
    g = await grup_olustur(antrenor=a)
    o = await ogrenci_olustur()
    o2 = await ogrenci_olustur("Veli", "Kaya")
    await uye_yap(o, g)
    await uye_yap(o2, g)
    ot = await oturum_olustur(g)
    y = await yoklama_put(istemci, ba, ot, [
        {"ogrenci_id": str(o.id), "durum": "gelmedi", "sebep": "raporlu", "aciklama": "  Ateşi var  "},
        {"ogrenci_id": str(o2.id), "durum": "geldi"},
    ])
    assert y.status_code == 200, y.text
    for b in (ba, yonetici):
        satirlar = {s["ad"]: s for s in (await istemci.get(f"/api/oturumlar/{ot.id}", headers=b)).json()["ogrenciler"]}
        assert (satirlar["Ali"]["yoklama"], satirlar["Ali"]["sebep"], satirlar["Ali"]["aciklama"]) == ("gelmedi", "raporlu", "Ateşi var")
        assert (satirlar["Veli"]["sebep"], satirlar["Veli"]["aciklama"]) == (None, None)


async def test_veli_sebebi_gorur_aciklamayi_asla(istemci, yonetici):
    _, cocuk = await veli_ve_cocuk()
    g = await grup_olustur()
    await uye_yap(cocuk, g)
    ot = await oturum_olustur(g, BUGUN - timedelta(days=1))
    y = await yoklama_put(istemci, yonetici, ot, [
        {"ogrenci_id": str(cocuk.id), "durum": "gelmedi", "sebep": "yarisma", "aciklama": "GizliAntrenorNotu"},
    ])
    assert y.status_code == 200, y.text
    b = await baslik(istemci)
    yanit = await istemci.get(f"/api/benim/cocuklar/{cocuk.id}", headers=b)
    assert yanit.status_code == 200
    d = yanit.json()
    ders = [x for x in d["gecmis_dersler"] if x["oturum_id"] == str(ot.id)][0]
    assert (ders["yoklama"], ders["sebep"]) == ("gelmedi", "yarisma")
    assert "aciklama" not in ders
    assert "GizliAntrenorNotu" not in yanit.text and '"aciklama"' not in yanit.text
    liste = await istemci.get("/api/benim/cocuklar", headers=b)
    assert "GizliAntrenorNotu" not in liste.text and '"aciklama"' not in liste.text
    # Yönetici devam özeti açıklamayı taşır; veli ucu devam özeti kullanmaz.
    dv = (await istemci.get(f"/api/ogrenciler/{cocuk.id}/devam", headers=yonetici)).json()
    assert dv["son_dersler"][0]["aciklama"] == "GizliAntrenorNotu"
    assert (await istemci.get(f"/api/benim/cocuklar/{cocuk.id}/devam", headers=b)).status_code == 404


# ---------- bildirim ----------


async def kisili_ogrenci():
    o, ot, _ = await ortam()
    async with SessionLocal() as s:
        s.add(IletisimKisisi(ogrenci_id=o, rol=IletisimRolu.anne, ad_soyad="Anne", telefon="+905551112233",
                             birincil=True, whatsapp_izni=True))
        await s.commit()
    return o, ot


async def gelmedi_bildirimleri():
    async with SessionLocal() as s:
        return list((await s.execute(select(Bildirim).where(Bildirim.sablon == "ders_gelmedi"))).scalars())


async def test_bildirim_sebebi_yazar_ve_suresinde_sebep_degisince_guncellenir():
    o, ot = await kisili_ogrenci()
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2), S.raporlu)
    [b] = await gelmedi_bildirimleri()
    async with SessionLocal() as s:
        m = await bsvc.metin_olustur(s, await s.get(Bildirim, b.id))
    assert "dersine katılmadı (Raporlu)." in m and "ay sonuna kadar" in m
    # Geri alma penceresinde habersize çevrilir: aynı satır yeni sebeple bekler.
    await isaretle(o, ot, YoklamaDurum.gelmedi, t(2) + timedelta(minutes=1), S.devamsiz)
    [b] = await gelmedi_bildirimleri()
    assert b.durum == BildirimDurum.bekliyor and b.parametreler["sebep"] == "devamsiz"
    async with SessionLocal() as s:
        m = await bsvc.metin_olustur(s, b)
        mw = await bsvc.metin_olustur(s, b, soylenis=True)
    assert "(Habersiz)" in m and "ders hakkı kullanılmış sayılır" in m and "(Habersiz)" in mw
    # Geldi'ye düzeltilirse iptal olur (3 dakikalık geri alma davranışı değişmedi).
    await isaretle(o, ot, YoklamaDurum.geldi, t(2) + timedelta(minutes=2))
    assert {x.durum for x in await gelmedi_bildirimleri()} == {BildirimDurum.iptal}


def test_sebepsiz_eski_bildirim_metni_degismedi():
    assert bsvc.gelmedi_alanlari(None) == {"sebep": "", "sonuc": "Telafi hakkı tanımlanacaktır."}


# ---------- devam özeti ----------


async def test_devam_ozeti_sebep_sayilari(istemci, yonetici):
    g = await grup_olustur()
    o = await ogrenci_olustur()
    await uye_yap(o, g)
    for i, (durum, sebep) in enumerate([
        ("geldi", None), ("gelmedi", S.izinli), ("gelmedi", S.izinli), ("gelmedi", S.devamsiz), ("gelmedi", None),
    ]):
        ot = await oturum_olustur(g, BUGUN - timedelta(days=i + 1), durum=OturumDurum.yapildi)
        await kaydet(Yoklama(oturum_id=ot.id, ogrenci_id=o.id, durum=YoklamaDurum(durum), sebep=sebep))
    d = (await istemci.get(f"/api/ogrenciler/{o.id}/devam", headers=yonetici)).json()
    assert (d["katildi"], d["gelmedi"], d["oran"]) == (1, 4, 20)
    assert d["gelmedi_sebepleri"] == {"izinli": 2, "raporlu": 0, "yarisma": 0, "devamsiz": 1, "bilinmiyor": 1}
    assert [s["sebep"] for s in d["son_dersler"]] == [None, "izinli", "izinli", "devamsiz", None]
