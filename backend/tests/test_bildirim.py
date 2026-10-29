"""Bildirim kuyruğu: olay -> kuyruk kuralları, tercihler, metinler. Gönderim yoktur; saat enjekte edilir."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app import bildirim as bsvc
from app import ders_hakki
from app.db import SessionLocal
from app.models import (
    Bildirim,
    BildirimDurum,
    BildirimKanal,
    BildirimTercihi,
    DenetimKaydi,
    DersHakkiHareketi,
    DersOturumu,
    Grup,
    HareketTuru,
    IletisimKisisi,
    IletisimRolu,
    Ogrenci,
    OgrenciPaketi,
    OgrenciPaketiDurum,
    Paket,
    PaketTuru,
    Rol,
    Sayac,
    TelafiPlani,
    Yoklama,
    YoklamaDurum,
)
from tests.conftest import SIFRE, kullanici_olustur
from tests.test_yoklama import (
    BUGUN,
    antrenor_hesabi,
    govde,
    giris,
    grup_olustur,
    oturum_olustur,
    uye_yap,
    yonetici,  # noqa: F401  (fixture)
)

T0 = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)


async def ortam(*, izin=True, hesap=True, birincil=True, ikinci=False, ad="Deniz"):
    """Öğrenci + birincil kişi (+ isteğe bağlı ikinci kişi). (ogrenci_id, kullanici_id|None, kisi_id) döner."""
    k = await kullanici_olustur(f"{ad.lower()}@veli.com", Rol.veli) if hesap else None
    async with SessionLocal() as s:
        o = Ogrenci(ad=ad, soyad="Test", dogum_tarihi=date(2016, 1, 3))
        s.add(o)
        await s.flush()
        kisi = IletisimKisisi(
            ogrenci_id=o.id, rol=IletisimRolu.anne, ad_soyad="Anne", telefon="+905551112233",
            birincil=birincil, whatsapp_izni=izin, kullanici_id=k.id if (k and birincil) else None,
        )
        s.add(kisi)
        if ikinci:
            s.add(IletisimKisisi(
                ogrenci_id=o.id, rol=IletisimRolu.baba, ad_soyad="Baba", telefon="+905551112244",
                birincil=False, whatsapp_izni=True,
            ))
        await s.commit()
        return o.id, (k.id if k else None), kisi.id


async def oturum(gun=0):
    async with SessionLocal() as s:
        g = (await s.execute(select(Grup))).scalars().first()
        if g is None:
            g = Grup(ad="A", kontenjan=10)
            s.add(g)
            await s.flush()
        ot = DersOturumu(grup_id=g.id, tarih=date(2026, 11, 2) + timedelta(days=gun), baslangic=time(17), bitis=time(18, 30))
        s.add(ot)
        await s.commit()
        return ot.id


async def isaretle(ogrenci_id, oturum_id, durum, an=T0, telafi_mi=False):
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


async def bildirimler(sablon=None):
    async with SessionLocal() as s:
        q = select(Bildirim).order_by(Bildirim.id)
        if sablon:
            q = q.where(Bildirim.sablon == sablon)
        return list((await s.execute(q)).scalars())


async def _ogrenci(ogrenci_id):
    async with SessionLocal() as s:
        return await s.get(Ogrenci, ogrenci_id)


async def yukle(ogrenci_id, miktar, paket_durum=OgrenciPaketiDurum.odendi):
    """Ödenmiş paket + ders yüklemesi."""
    async with SessionLocal() as s:
        p = Paket(ad="8 ders", tur=PaketTuru.aylik, ders_sayisi=8, sure_ay=1, varsayilan_fiyat=Decimal("100"))
        s.add(p)
        await s.flush()
        if paket_durum is not None:
            s.add(OgrenciPaketi(
                ogrenci_id=ogrenci_id, paket_id=p.id, ders_sayisi=8, liste_fiyati=Decimal("100"),
                uygulanan_fiyat=Decimal("100"), durum=paket_durum,
            ))
        s.add(DersHakkiHareketi(ogrenci_id=ogrenci_id, sayac=Sayac.normal, miktar=miktar, tur=HareketTuru.paket_yuklemesi))
        await s.commit()


# ---------- ders_gelmedi ----------


async def test_gelmedi_birincil_kisiye_geri_alma_penceresiyle_kuyruga_girer():
    o, k, kisi = await ortam(ikinci=True)
    await isaretle(o, await oturum(), YoklamaDurum.gelmedi)
    liste = await bildirimler()
    assert {b.kanal for b in liste} == {BildirimKanal.whatsapp, BildirimKanal.push}
    assert all(b.alici_iletisim_id == kisi and b.sablon == "ders_gelmedi" for b in liste)
    assert all(b.durum == BildirimDurum.bekliyor and b.planli_zaman == T0 + bsvc.GERI_ALMA_SURESI for b in liste)
    assert liste[0].parametreler["tarih"] == "2026-11-02" and liste[0].parametreler["baslangic"] == "17:00"
    assert "ad" not in liste[0].parametreler


async def test_whatsapp_yalniz_izinle():
    o, k, _ = await ortam(izin=False)
    await isaretle(o, await oturum(), YoklamaDurum.gelmedi)
    assert [b.kanal for b in await bildirimler()] == [BildirimKanal.push]


async def test_push_yalniz_hesapli_kisiye():
    o, k, _ = await ortam(hesap=False)
    await isaretle(o, await oturum(), YoklamaDurum.gelmedi)
    assert [b.kanal for b in await bildirimler()] == [BildirimKanal.whatsapp]


async def test_birincil_kisi_yoksa_kuyruk_bos():
    o, k, _ = await ortam(birincil=False)
    await isaretle(o, await oturum(), YoklamaDurum.gelmedi)
    assert await bildirimler() == []


async def test_duzeltme_bekleyeni_iptal_eder_tekrar_gelmedi_yeniden_etkinlestirir():
    o, k, _ = await ortam()
    ot = await oturum()
    await isaretle(o, ot, YoklamaDurum.gelmedi)
    await isaretle(o, ot, YoklamaDurum.geldi, T0 + timedelta(minutes=1))
    assert {b.durum for b in await bildirimler()} == {BildirimDurum.iptal}
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0 + timedelta(minutes=2))
    liste = await bildirimler()
    assert len(liste) == 2 and {b.durum for b in liste} == {BildirimDurum.bekliyor}
    assert all(b.planli_zaman == T0 + timedelta(minutes=2) + bsvc.GERI_ALMA_SURESI for b in liste)


async def test_gonderilmis_bildirim_iptal_edilmez():
    o, k, _ = await ortam()
    ot = await oturum()
    await isaretle(o, ot, YoklamaDurum.gelmedi)
    async with SessionLocal() as s:
        for b in (await s.execute(select(Bildirim))).scalars():
            b.durum = BildirimDurum.gonderildi
        await s.commit()
    await isaretle(o, ot, YoklamaDurum.geldi, T0 + timedelta(hours=1))
    assert {b.durum for b in await bildirimler()} == {BildirimDurum.gonderildi}


async def test_http_yoklama_duzeltmesi_bekleyeni_iptal_eder(istemci, yonetici):  # noqa: F811
    g = await grup_olustur()
    ogr, _, _ = await ortam()
    await uye_yap(await _ogrenci(ogr), g)
    ot = await oturum_olustur(g)

    async def yoklama(durum):
        y = await istemci.put(
            f"/api/oturumlar/{ot.id}/yoklama", json=[{"ogrenci_id": str(ogr), "durum": durum}], headers=yonetici
        )
        assert y.status_code == 200, y.text

    await yoklama("gelmedi")
    assert {b.durum for b in await bildirimler()} == {BildirimDurum.bekliyor}
    await yoklama("geldi")
    assert {b.durum for b in await bildirimler()} == {BildirimDurum.iptal}


async def test_telafi_dersinde_gelmedi_bildirim_yok():
    o, k, _ = await ortam()
    ot = await oturum()
    async with SessionLocal() as s:
        s.add(TelafiPlani(oturum_id=ot, ogrenci_id=o))
        await s.commit()
    await isaretle(o, ot, YoklamaDurum.gelmedi, telafi_mi=True)
    assert await bildirimler() == []


# ---------- bakiye olayları ----------


async def test_bakiye_2_olunca_azaldi():
    o, k, _ = await ortam()
    await yukle(o, 4)
    await isaretle(o, await oturum(0), YoklamaDurum.geldi)  # 3
    assert await bildirimler() == []
    await isaretle(o, await oturum(1), YoklamaDurum.geldi, T0 + timedelta(days=1))  # 2
    liste = await bildirimler("ders_hakki_azaldi")
    assert len(liste) == 2 and liste[0].parametreler == {"bakiye": 2} and liste[0].planli_zaman == T0 + timedelta(days=1)


async def test_bakiye_0_odenmis_paketle_bitti_ve_tekrarlanmaz():
    o, k, _ = await ortam()
    await yukle(o, 1)
    await isaretle(o, await oturum(0), YoklamaDurum.geldi)  # 0
    assert len(await bildirimler("ders_hakki_bitti")) == 2
    await isaretle(o, await oturum(1), YoklamaDurum.geldi, T0 + timedelta(days=1))  # -1: yine yok
    assert len(await bildirimler("ders_hakki_bitti")) == 2
    # Yeni yükleme sonrası yeniden bitince yeniden bildirilir.
    await yukle(o, 1)
    await isaretle(o, await oturum(2), YoklamaDurum.geldi, T0 + timedelta(days=2))
    assert len(await bildirimler("ders_hakki_bitti")) == 4


async def test_bitti_odenmis_paket_yoksa_yok():
    o, k, _ = await ortam()
    await yukle(o, 1, paket_durum=OgrenciPaketiDurum.odeme_bekliyor)
    await isaretle(o, await oturum(0), YoklamaDurum.geldi)
    assert await bildirimler("ders_hakki_bitti") == []


async def test_devamsizlik_hareketi_de_bakiye_olayi_uretir():
    o, k, _ = await ortam()
    await yukle(o, 3)
    await isaretle(o, await oturum(0), YoklamaDurum.gelmedi)
    assert await bildirimler("ders_hakki_azaldi") == []  # hak 1 saat sonra düşer
    async with SessionLocal() as s:
        assert await ders_hakki.bekleyen_devamsizliklari_isle(s, T0 + timedelta(hours=1)) == 1
        await s.commit()
    assert len(await bildirimler("ders_hakki_azaldi")) == 2
    assert len(await bildirimler("ders_gelmedi")) == 2


async def test_ayni_yoklama_tekrar_islenirse_cift_kayit_olmaz():
    o, k, _ = await ortam()
    await yukle(o, 3)
    ot = await oturum(0)
    await isaretle(o, ot, YoklamaDurum.geldi)
    await isaretle(o, ot, YoklamaDurum.gelmedi, T0 + timedelta(minutes=1))
    await isaretle(o, ot, YoklamaDurum.geldi, T0 + timedelta(minutes=2))
    assert len(await bildirimler("ders_hakki_azaldi")) == 2


# ---------- tercihler ----------


async def test_tercih_kapaliysa_kuyruk_bos():
    o, k, _ = await ortam()
    await yukle(o, 2)
    async with SessionLocal() as s:
        s.add(BildirimTercihi(kullanici_id=k, ders_gelmedi=False, ders_hakki=False))
        await s.commit()
    await isaretle(o, await oturum(0), YoklamaDurum.gelmedi)
    await isaretle(o, await oturum(1), YoklamaDurum.geldi, T0 + timedelta(days=1))
    assert await bildirimler() == []


async def test_kanal_tercihi():
    o, k, _ = await ortam()
    async with SessionLocal() as s:
        s.add(BildirimTercihi(kullanici_id=k, whatsapp=False))
        await s.commit()
    await isaretle(o, await oturum(), YoklamaDurum.gelmedi)
    assert [b.kanal for b in await bildirimler()] == [BildirimKanal.push]


# ---------- gönderilecekleri al, metin ----------


async def test_gonderilecekleri_al_yalniz_zamani_gelen_bekleyenler():
    o, k, _ = await ortam()
    await isaretle(o, await oturum(), YoklamaDurum.gelmedi)
    async with SessionLocal() as s:
        assert await bsvc.gonderilecekleri_al(s, T0 + timedelta(minutes=2), 10) == []
        assert len(await bsvc.gonderilecekleri_al(s, T0 + timedelta(minutes=3), 10)) == 2
        assert len(await bsvc.gonderilecekleri_al(s, T0 + timedelta(minutes=3), 1)) == 1


async def test_metin_olustur_her_sablon():
    o, k, _ = await ortam(ad="Deniz")
    async with SessionLocal() as s:
        def b(sablon, p):
            return Bildirim(ogrenci_id=o, alici_iletisim_id=None, kanal=BildirimKanal.push, sablon=sablon, parametreler=p)

        m = await bsvc.metin_olustur(s, b("ders_gelmedi", {"tarih": "2026-11-02", "baslangic": "17:00"}))
        assert "Deniz" in m and "02.11.2026 17:00" in m and "{" not in m
        m = await bsvc.metin_olustur(s, b("ders_hakki_azaldi", {"bakiye": 2}))
        assert "Deniz" in m and "2 ders hakkı kaldı" in m
        m = await bsvc.metin_olustur(s, b("ders_hakki_bitti", {"bakiye": 0}))
        assert "Deniz" in m and "bitti" in m
    assert set(bsvc.SABLONLAR) == {"ders_gelmedi", "ders_hakki_azaldi", "ders_hakki_bitti", "duyuru"}


# ---------- API ----------


async def test_tercih_api_yetki(istemci):
    assert (await istemci.get("/api/benim/bildirim-tercihleri")).status_code == 401
    yon = await giris(istemci, "admin@kulup.com", Rol.admin)
    ant, _ = await antrenor_hesabi(istemci, "hoca@kulup.com", "Hoca")
    for h in (yon, ant):
        assert (await istemci.get("/api/benim/bildirim-tercihleri", headers=h)).status_code == 403
        assert (await istemci.put("/api/benim/bildirim-tercihleri", json={}, headers=h)).status_code == 403


async def test_tercih_api_gidis_donus_ve_denetim(istemci):
    o, k, _ = await ortam(izin=False, ad="Ece")
    y = await istemci.post("/api/auth/login", json={"giris": "ece@veli.com", "sifre": SIFRE})
    b = {"Authorization": f"Bearer {y.json()['access_token']}"}
    varsayilan = (await istemci.get("/api/benim/bildirim-tercihleri", headers=b)).json()
    assert varsayilan == {"ders_gelmedi": True, "ders_hakki": True, "whatsapp": True, "push": True, "whatsapp_izni_var": False}
    yeni = {"ders_gelmedi": False, "ders_hakki": True, "whatsapp": False, "push": True}
    y = await istemci.put("/api/benim/bildirim-tercihleri", json=yeni, headers=b)
    assert y.status_code == 200 and y.json() == {**yeni, "whatsapp_izni_var": False}
    assert (await istemci.get("/api/benim/bildirim-tercihleri", headers=b)).json() == y.json()
    assert (await istemci.put("/api/benim/bildirim-tercihleri", json={**yeni, "x": 1}, headers=b)).status_code == 422
    async with SessionLocal() as s:
        log = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "bildirim_tercihi_guncellendi"))).scalar_one()
        assert log.kullanici_id == k
