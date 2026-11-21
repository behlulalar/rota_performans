"""Ek ders (dilim 2): var olan derse ücretsiz katılım. Defteri etkilemez, telafi hakkı ayırmaz; yetki telafi ile aynı."""
import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import bildirim as bsvc
from app import ders_hakki
from app.db import SessionLocal
from app.models import (
    BildirimDurum,
    DenetimKaydi,
    DersHakkiHareketi,
    KatilimTuru,
    Ogrenci,
    OgrenciDurum,
    OturumDurum,
    TelafiPlani,
    Yoklama,
    YoklamaDurum,
)
from app.oturumlar import simdi
from tests.test_antrenor_telafi import YETKISIZ_GRUP, YETKISIZ_OTURUM, bildirimli, hata, hakli, kurulum
from tests.test_bildirim import bildirimler
from tests.test_devam import _ders
from tests.test_telafi import detay, duzelt, gun, hakli_ogrenci, plan_url
from tests.test_veli_paneli import baslik, veli_ve_cocuk
from tests.test_yoklama import (
    BUGUN,
    govde,
    grup_olustur,
    kaydet,
    ogrenci_olustur,
    oturum_olustur,
    uye_yap,
    yonetici,  # noqa: F401  (fixture)
)


def ek_url(ot):
    return f"/api/oturumlar/{ot.id}/ek-ders"


def pl(o, tasinan=None):
    g = {"ogrenci_id": str(o.id)}
    if tasinan is not None:
        g["tasinan_oturum_id"] = str(tasinan.id)
    return g


async def planlar():
    async with SessionLocal() as s:
        return list((await s.execute(select(TelafiPlani))).scalars())


async def hareketler():
    async with SessionLocal() as s:
        return list((await s.execute(select(DersHakkiHareketi))).scalars())


async def ek_ogrenci(istemci, yonetici, grup, ad="Ali", telafi=0):
    o = await hakli_ogrenci(istemci, yonetici, telafi=telafi, ad=ad)
    await uye_yap(o, grup)
    return o


async def test_yonetici_planlar_hak_gerekmez_denetim_ve_tur(istemci, yonetici):
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    o = await ek_ogrenci(istemci, yonetici, a1)  # telafi hakkı YOK
    ot = await oturum_olustur(a2, gun(2))
    y = await istemci.post(ek_url(ot), json=pl(o), headers=yonetici)
    assert y.status_code == 200, y.text
    satir = y.json()["ogrenciler"][0]
    assert (satir["telafi_mi"], satir["ek_ders_mi"]) == (False, True) and y.json()["ogrenci_sayisi"] == 1
    assert [p.tur for p in await planlar()] == [KatilimTuru.ek_ders]
    async with SessionLocal() as s:
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ek_ders_planlandi"))).scalar_one()
    assert k.hedef_id == str(ot.id) and k.detay == {"ogrenci_id": str(o.id)}
    # Planlar uç noktası tür taşır.
    lst = (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-planlari", headers=yonetici)).json()
    assert [p["tur"] for p in lst] == ["ek_ders"]
    # Kaldır.
    y = await istemci.delete(f"{ek_url(ot)}/{o.id}", headers=yonetici)
    assert y.status_code == 200 and y.json()["ogrenciler"] == []
    async with SessionLocal() as s:
        assert (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ek_ders_cikarildi"))).scalar_one()
    await hata(await istemci.delete(f"{ek_url(ot)}/{o.id}", headers=yonetici), 404, "Ek ders planı bulunamadı")


async def test_hatalar(istemci, yonetici):
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    o = await ek_ogrenci(istemci, yonetici, a1)
    ot = await oturum_olustur(a2, gun(2))
    gecmis = await oturum_olustur(a2, gun(-1))
    iptal = await oturum_olustur(a2, gun(3), durum=OturumDurum.iptal)
    kendi = await oturum_olustur(a1, gun(2))
    await hata(await istemci.post(ek_url(ot), json={"ogrenci_id": "00000000-0000-0000-0000-000000000000"}, headers=yonetici), 404, "Öğrenci bulunamadı")
    await hata(await istemci.post(ek_url(gecmis), json=pl(o), headers=yonetici), 422, "Geçmiş derse ek ders planlanamaz")
    await hata(await istemci.post(ek_url(iptal), json=pl(o), headers=yonetici), 422, "İptal edilmiş derse ek ders planlanamaz")
    await hata(await istemci.post(ek_url(kendi), json=pl(o), headers=yonetici), 422, "Öğrenci bu grubun üyesi, ek ders gerekmez")
    pasif = await ogrenci_olustur("Pasif", "P")
    async with SessionLocal() as s:
        (await s.get(Ogrenci, pasif.id)).durum = OgrenciDurum.pasif
        await s.commit()
    y = await istemci.post(ek_url(ot), json=pl(pasif), headers=yonetici)
    assert (y.status_code, y.json()["detail"]) == (422, "Pasif öğrenci için ek ders planlanamaz")
    assert (await istemci.post(ek_url(ot), json=pl(o), headers=yonetici)).status_code == 200
    await hata(await istemci.post(ek_url(ot), json=pl(o), headers=yonetici), 409, "Öğrenci bu derste zaten var")


async def test_ayni_derste_hem_telafi_hem_ek_ders_olmaz(istemci, yonetici):
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    o = await ek_ogrenci(istemci, yonetici, a1, telafi=2)
    ot = await oturum_olustur(a2, gun(2))
    assert (await istemci.post(plan_url(ot), json=pl(o), headers=yonetici)).status_code == 200
    await hata(await istemci.post(ek_url(ot), json=pl(o), headers=yonetici), 409, "Öğrenci bu derste zaten var")
    # Tersi: önce ek ders, sonra telafi.
    ot2 = await oturum_olustur(a2, gun(3))
    assert (await istemci.post(ek_url(ot2), json=pl(o), headers=yonetici)).status_code == 200
    await hata(await istemci.post(plan_url(ot2), json=pl(o), headers=yonetici), 409, "Öğrenci bu derste zaten var")
    # Telafi uçları ek ders planını göremez/silemez.
    await hata(await istemci.delete(f"{plan_url(ot2)}/{o.id}", headers=yonetici), 404, "Telafi planı bulunamadı")
    await hata(await istemci.delete(f"{ek_url(ot)}/{o.id}", headers=yonetici), 404, "Ek ders planı bulunamadı")


async def test_kontenjan_ve_adaylar(istemci, yonetici):
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    a2.kontenjan = 1
    async with SessionLocal() as s:
        g = await s.get(type(a2), a2.id)
        g.kontenjan = 1
        await s.commit()
    o1 = await ek_ogrenci(istemci, yonetici, a1, "Ali")
    o2 = await ek_ogrenci(istemci, yonetici, a1, "Veli")
    ot = await oturum_olustur(a2, gun(2))
    kendi = await oturum_olustur(a1, gun(2))
    adaylar = (await istemci.get(f"/api/ogrenciler/{o1.id}/ek-ders-adaylari", headers=yonetici)).json()
    # Hak süzgeci yok (hiç telafi hakkı olmasa da listelenir); kendi grubu hariç.
    assert [(x["oturum"]["id"], x["bos_yer"]) for x in adaylar] == [(str(ot.id), 1)]
    assert (await istemci.post(ek_url(ot), json=pl(o1), headers=yonetici)).status_code == 200
    await hata(await istemci.post(ek_url(ot), json=pl(o2), headers=yonetici), 409, "Bu derste boş yer yok")
    # Planlı ders aday listesinden düşer, dolu ders de.
    for o in (o1, o2):
        assert (await istemci.get(f"/api/ogrenciler/{o.id}/ek-ders-adaylari", headers=yonetici)).json() == []
    assert kendi
    y = await istemci.get(f"/api/ogrenciler/{o1.id}/ek-ders-adaylari?baslangic=2026-01-01&bitis=2026-03-01", headers=yonetici)
    assert (y.status_code, y.json()["detail"]) == (422, "Aralık en çok 31 gün olabilir")


async def test_tasima_atomik(istemci, yonetici):
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    o = await ek_ogrenci(istemci, yonetici, a1)
    eski = await oturum_olustur(a2, gun(2))
    yeni = await oturum_olustur(a2, gun(3))
    dolu_iptal = await oturum_olustur(a2, gun(4), durum=OturumDurum.iptal)
    assert (await istemci.post(ek_url(eski), json=pl(o), headers=yonetici)).status_code == 200
    # Reddedilen taşıma eski planı korur.
    await hata(await istemci.post(ek_url(dolu_iptal), json=pl(o, eski), headers=yonetici), 422, "İptal edilmiş derse ek ders planlanamaz")
    assert [p.oturum_id for p in await planlar()] == [eski.id]
    y = await istemci.post(ek_url(yeni), json=pl(o, eski), headers=yonetici)
    assert y.status_code == 200
    assert [p.oturum_id for p in await planlar()] == [yeni.id]
    async with SessionLocal() as s:
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ek_ders_tasindi"))).scalar_one()
    assert k.detay == {"ogrenci_id": str(o.id), "eski_oturum_id": str(eski.id)}
    await hata(await istemci.post(ek_url(yeni), json=pl(o, eski), headers=yonetici), 404, "Ek ders planı bulunamadı")
    await hata(await istemci.post(ek_url(yeni), json=pl(o, yeni), headers=yonetici), 409, "Öğrenci bu derste zaten var")
    # Telafi planı ek ders ucuyla taşınamaz.
    t = await ek_ogrenci(istemci, yonetici, a1, "Tel", telafi=1)
    tot = await oturum_olustur(a2, gun(5))
    assert (await istemci.post(plan_url(tot), json=pl(t), headers=yonetici)).status_code == 200
    await hata(await istemci.post(ek_url(yeni), json=pl(t, tot), headers=yonetici), 404, "Ek ders planı bulunamadı")
    # Yoklaması alınmış ek ders taşınamaz/kaldırılamaz.
    bugun_ot = await oturum_olustur(a2, BUGUN)
    assert (await istemci.post(ek_url(bugun_ot), json=pl(o), headers=yonetici)).status_code == 200
    assert (await istemci.put(f"/api/oturumlar/{bugun_ot.id}/yoklama", json=govde((o, "geldi")), headers=yonetici)).status_code == 200
    await hata(await istemci.post(ek_url(yeni), json=pl(o, bugun_ot), headers=yonetici), 409, "Yoklaması alınmış ek ders geri alınamaz")
    await hata(await istemci.delete(f"{ek_url(bugun_ot)}/{o.id}", headers=yonetici), 409, "Yoklaması alınmış ek ders geri alınamaz")


async def test_ek_ders_telafi_hakki_ayirmaz_ve_suresini_etkilemez(istemci, yonetici):
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    o = await ek_ogrenci(istemci, yonetici, a1, telafi=1)
    ileri = await oturum_olustur(a2, gun(2))
    assert (await istemci.post(ek_url(ileri), json=pl(o), headers=yonetici)).status_code == 200
    assert await detay(istemci, yonetici, o) == {"normal": 0, "telafi": 1, "kullanilabilir_telafi": 1}
    # Aynı plan telafi olsaydı hakkı ayırırdı (kontrol): türü çevirince kullanılabilir 0 olur.
    async with SessionLocal() as s:
        p = (await s.execute(select(TelafiPlani).where(TelafiPlani.oturum_id == ileri.id))).scalar_one()
        p.tur = KatilimTuru.telafi
        await s.commit()
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 0
    # Ek ders hiç defter satırı yazmadı: yalnız manuel düzeltme var.
    assert {h.tur.value for h in await hareketler()} == {"manuel_duzeltme"}


async def yoklama_ac(istemci, yonetici, ad="Ali", gelmedi_sebep="izinli"):
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    o = await ek_ogrenci(istemci, yonetici, a1, ad=ad)
    ot = await oturum_olustur(a2, BUGUN)
    assert (await istemci.post(ek_url(ot), json=pl(o), headers=yonetici)).status_code == 200
    return o, ot


async def test_ek_derste_geldi_gelmedi_defter_yazmaz_isci_atlar_bildirim_yok(istemci, yonetici):
    from tests.test_bildirim import ortam
    ogr_id, _, _ = await ortam()
    from app.models import Ogrenci
    async with SessionLocal() as s:
        o = await s.get(Ogrenci, ogr_id)
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    await uye_yap(o, a1)
    ot = await oturum_olustur(a2, BUGUN)
    assert (await istemci.post(ek_url(ot), json=pl(o), headers=yonetici)).status_code == 200
    ilk_bildirim = len(await bildirimler())
    # Gelmedi: sebepsiz 422, sebepli kabul; defter ve bildirim yok, yoklama ek_ders_mi.
    y = await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=[{"ogrenci_id": str(o.id), "durum": "gelmedi"}], headers=yonetici)
    assert y.status_code == 422
    y = await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o, "gelmedi"), sebep="devamsiz"), headers=yonetici)
    assert y.status_code == 200 and y.json()["ogrenciler"][0]["yoklama"] == "gelmedi"
    async with SessionLocal() as s:
        yk = (await s.execute(select(Yoklama))).scalar_one()
        assert (yk.ek_ders_mi, yk.telafi_mi, yk.hareket_islendi, yk.hareket_planli_zaman) == (True, False, True, None)
        assert await ders_hakki.bekleyen_devamsizliklari_isle(s, simdi() + timedelta(hours=5)) == 0
    assert await hareketler() == []
    # Geldi'ye düzeltme de defter yazmaz.
    y = await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o, "geldi")), headers=yonetici)
    assert y.status_code == 200
    assert await hareketler() == []
    assert len(await bildirimler()) == ilk_bildirim
    assert not [b for b in await bildirimler() if b.sablon in ("ders_gelmedi", "ders_hakki_azaldi", "ders_hakki_bitti")]
    assert await detay(istemci, yonetici, o) == {"normal": 0, "telafi": 0, "kullanilabilir_telafi": 0}


async def test_check_telafi_ve_ek_ders_birlikte_olamaz(istemci, yonetici):
    a1 = await grup_olustur("A1")
    o = await ogrenci_olustur()
    ot = await oturum_olustur(a1, BUGUN)
    with pytest.raises(IntegrityError):
        await kaydet(Yoklama(oturum_id=ot.id, ogrenci_id=o.id, durum=YoklamaDurum.geldi, telafi_mi=True, ek_ders_mi=True))


async def test_devam_ek_ders_orana_girmez_son_derslerde_var(istemci, yonetici):
    g = await grup_olustur("U10")
    o = await ogrenci_olustur()
    await uye_yap(o, g)
    await _ders(g, o, 10, "geldi")
    await _ders(g, o, 5, "gelmedi")
    ot = await oturum_olustur(g, BUGUN - timedelta(days=2), durum=OturumDurum.yapildi)
    await kaydet(Yoklama(oturum_id=ot.id, ogrenci_id=o.id, durum=YoklamaDurum.gelmedi, ek_ders_mi=True))
    d = (await istemci.get(f"/api/ogrenciler/{o.id}/devam", headers=yonetici)).json()
    assert (d["katildi"], d["gelmedi"], d["oran"]) == (1, 1, 50)
    assert (d["son30_katildi"], d["son30_gelmedi"]) == (1, 1) and d["ard_arda_gelmedi"] == 1
    assert sum(d["gelmedi_sebepleri"].values()) == d["gelmedi"]
    assert [(s["ek_ders_mi"], s["durum"]) for s in d["son_dersler"]] == [(True, "gelmedi"), (False, "gelmedi"), (False, "geldi")]


async def test_veli_listesinde_ek_ders_mi(istemci):
    k, o = await veli_ve_cocuk()
    diger = await grup_olustur("DIGER")
    ot = await oturum_olustur(diger, BUGUN + timedelta(days=2))
    ot2 = await oturum_olustur(diger, BUGUN + timedelta(days=3))
    await kaydet(TelafiPlani(oturum_id=ot.id, ogrenci_id=o.id, tur=KatilimTuru.ek_ders), TelafiPlani(oturum_id=ot2.id, ogrenci_id=o.id))
    b = await baslik(istemci)
    d = (await istemci.get(f"/api/benim/cocuklar/{o.id}", headers=b)).json()
    assert [(x["oturum_id"], x["telafi_mi"], x["ek_ders_mi"]) for x in d["yaklasan_dersler"]] == [
        (str(ot.id), False, True), (str(ot2.id), True, False),
    ]


async def test_antrenor_kapsami_ve_bugun_ek_ders_sayisi(istemci, yonetici):
    ba, a, bb, b, a1, a2, b1 = await kurulum(istemci)
    o = await hakli(istemci, yonetici, a1, telafi=0)
    yabanci = await hakli(istemci, yonetici, b1, telafi=0, ad="Yabanci")
    ot = await oturum_olustur(a2, BUGUN)
    baskasi = await oturum_olustur(b1, gun(2))
    # Kendi grubunun öğrencisi + kendi dersi: olur; denetim kullanıcısı antrenör.
    y = await istemci.post(ek_url(ot), json=pl(o), headers=ba)
    assert y.status_code == 200, y.text
    # Başka grubun öğrencisi: 403; başkasının dersi: 403.
    await hata(await istemci.post(ek_url(ot), json=pl(yabanci), headers=ba), 403, YETKISIZ_GRUP)
    await hata(await istemci.post(ek_url(baskasi), json=pl(o), headers=ba), 403, YETKISIZ_OTURUM)
    await hata(await istemci.delete(f"{ek_url(baskasi)}/{o.id}", headers=ba), 403, YETKISIZ_OTURUM)
    await hata(await istemci.get(f"/api/ogrenciler/{yabanci.id}/ek-ders-adaylari", headers=ba), 403, YETKISIZ_GRUP)
    # Adaylar yalnız kendi dersleri.
    await oturum_olustur(a2, gun(4))
    await oturum_olustur(b1, gun(4))
    adaylar = (await istemci.get(f"/api/ogrenciler/{o.id}/ek-ders-adaylari", headers=ba)).json()
    assert [x["oturum"]["grup"]["ad"] for x in adaylar] == ["A2"]
    # Bugün: telafi_sayisi ve ek_ders_sayisi ayrı sayılır.
    t = await hakli(istemci, yonetici, a1, telafi=1, ad="Telafili")
    assert (await istemci.post(plan_url(ot), json=pl(t), headers=ba)).status_code == 200
    bugun_ders = next(d for d in (await istemci.get("/api/antrenor/bugun", headers=ba)).json()["dersler"] if d["id"] == str(ot.id))
    assert (bugun_ders["telafi_sayisi"], bugun_ders["ek_ders_sayisi"]) == (1, 1)
    # Yerine bakan antrenör planlar; asıl antrenör planlayamaz.
    yerine = await oturum_olustur(b1, gun(5), antrenor=a)
    assert (await istemci.post(ek_url(yerine), json=pl(o), headers=ba)).status_code == 200
    await hata(await istemci.post(ek_url(yerine), json=pl(yabanci), headers=bb), 403, YETKISIZ_OTURUM)
    async with SessionLocal() as s:
        from app.models import Kullanici
        kul = (await s.execute(select(Kullanici).where(Kullanici.giris == "a@kulup.com"))).scalar_one()
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ek_ders_planlandi").order_by(DenetimKaydi.id))).scalars().first()
    assert k.kullanici_id == kul.id
    # Antrenör kaldırır.
    assert (await istemci.delete(f"{ek_url(ot)}/{o.id}", headers=ba)).status_code == 200


async def test_planlar_tur_ve_antrenor_telafi_ayrintisi(istemci, yonetici):
    ba, a, bb, b, a1, a2, b1 = await kurulum(istemci)
    o = await hakli(istemci, yonetici, a1, telafi=1)
    ek = await oturum_olustur(a2, gun(2))
    tel = await oturum_olustur(a2, gun(3))
    assert (await istemci.post(ek_url(ek), json=pl(o), headers=ba)).status_code == 200
    assert (await istemci.post(plan_url(tel), json=pl(o), headers=ba)).status_code == 200
    d = (await istemci.get(f"/api/antrenor/ogrenciler/{o.id}/telafi", headers=ba)).json()
    assert {p["tur"] for p in d["planlar"]} == {"telafi", "ek_ders"}
    assert d["kullanilabilir"] == 0  # tek hak telafi planıyla ayrıldı; ek ders hak ayırmadı


async def test_bildirimler_planlama_tasima_kaldirma(istemci, yonetici):
    ba, a1, a2, b1, o, kul_id, kisi_id = await bildirimli(istemci, yonetici)
    eski = await oturum_olustur(a2, gun(2))
    yeni = await oturum_olustur(a2, gun(3))
    once = simdi()
    assert (await istemci.post(ek_url(eski), json=pl(o), headers=ba)).status_code == 200
    liste = await bildirimler("ek_ders_planlandi")
    assert {b.kanal.value for b in liste} == {"whatsapp", "push"}
    assert all(b.alici_iletisim_id == kisi_id and b.durum == BildirimDurum.bekliyor for b in liste)
    assert all(timedelta(minutes=2) < b.planli_zaman - once < timedelta(minutes=4) for b in liste)
    async with SessionLocal() as s:
        metin = await bsvc.metin_olustur(s, liste[0])
    assert metin == f"Rota Performans Akademi: {o.ad} için {eski.tarih.strftime('%d.%m.%Y')} 00:00 A2 dersine ek ders planlandı."
    # Pencerede taşıma: eski iptal, yeni derse "planlandı".
    assert (await istemci.post(ek_url(yeni), json=pl(o, eski), headers=ba)).status_code == 200
    planlandi = await bildirimler("ek_ders_planlandi")
    assert [b.durum for b in planlandi if b.parametreler["oturum_id"] == str(eski.id)] == [BildirimDurum.iptal] * 2
    assert len([b for b in planlandi if b.durum == BildirimDurum.bekliyor and b.parametreler["oturum_id"] == str(yeni.id)]) == 2
    assert await bildirimler("ek_ders_tasindi") == []
    # Pencerede kaldırma: hiçbir şey gitmez. Telafi şablonları hiç kullanılmadı.
    assert (await istemci.delete(f"{ek_url(yeni)}/{o.id}", headers=ba)).status_code == 200
    assert all(b.durum == BildirimDurum.iptal for b in await bildirimler())
    assert await bildirimler("telafi_planlandi") == [] and await bildirimler("ek_ders_iptal_edildi") == []


async def test_bildirim_gonderilmis_plan_tasima_ve_kaldirma_metinleri(istemci, yonetici):
    ba, a1, a2, b1, o, kul_id, kisi_id = await bildirimli(istemci, yonetici)
    eski = await oturum_olustur(a2, gun(2))
    yeni = await oturum_olustur(a2, gun(3))
    assert (await istemci.post(ek_url(eski), json=pl(o), headers=yonetici)).status_code == 200
    async with SessionLocal() as s:  # gönderilmiş say
        for b in await bildirimler("ek_ders_planlandi"):
            (await s.get(type(b), b.id)).durum = BildirimDurum.gonderildi
        await s.commit()
    assert (await istemci.post(ek_url(yeni), json=pl(o, eski), headers=yonetici)).status_code == 200
    tasindi = await bildirimler("ek_ders_tasindi")
    assert len(tasindi) == 2
    async with SessionLocal() as s:
        metin = await bsvc.metin_olustur(s, tasindi[0])
    assert "ek ders" in metin and "taşındı" in metin and "telafi" not in metin
    assert (await istemci.delete(f"{ek_url(yeni)}/{o.id}", headers=yonetici)).status_code == 200
    iptal = await bildirimler("ek_ders_iptal_edildi")
    assert iptal and all(b.durum == BildirimDurum.bekliyor for b in iptal)
    # Telafi bildirimleri bundan etkilenmedi.
    assert await bildirimler("telafi_planlandi") == [] and await bildirimler("telafi_tasindi") == []


async def test_esanli_iki_ekleme_son_yeri_bir_kez_verir(istemci, yonetici):
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    async with SessionLocal() as s:
        g = await s.get(type(a2), a2.id)
        g.kontenjan = 1
        await s.commit()
    o1 = await ek_ogrenci(istemci, yonetici, a1, "Ali")
    o2 = await ek_ogrenci(istemci, yonetici, a1, "Veli")
    ot = await oturum_olustur(a2, gun(2))
    yanitlar = await asyncio.gather(
        istemci.post(ek_url(ot), json=pl(o1), headers=yonetici),
        istemci.post(ek_url(ot), json=pl(o2), headers=yonetici),
    )
    assert sorted(y.status_code for y in yanitlar) == [200, 409]
    assert len(await planlar()) == 1


async def _gonderildi_say():
    async with SessionLocal() as s:
        for b in await bildirimler():
            (await s.get(type(b), b.id)).durum = BildirimDurum.gonderildi
        await s.commit()


async def test_ders_iptali_plan_sahiplerine_bildirir_ek_ders(istemci, yonetici):
    ba, a1, a2, b1, o, kul_id, kisi_id = await bildirimli(istemci, yonetici)
    ot = await oturum_olustur(a2, gun(2))
    assert (await istemci.post(ek_url(ot), json=pl(o), headers=yonetici)).status_code == 200
    await _gonderildi_say()
    assert (await istemci.post(f"/api/oturumlar/{ot.id}/iptal", headers=yonetici)).status_code == 200
    assert await planlar() == []
    iptal = await bildirimler("ek_ders_iptal_edildi")
    assert len(iptal) == 2 and all(b.durum == BildirimDurum.bekliyor for b in iptal)
    assert await bildirimler("telafi_iptal_edildi") == []


async def test_ders_iptali_plan_sahiplerine_bildirir_telafi(istemci, yonetici):
    ba, a1, a2, b1, o, kul_id, kisi_id = await bildirimli(istemci, yonetici)
    ot = await oturum_olustur(a2, gun(2))
    assert (await istemci.post(plan_url(ot), json=pl(o), headers=yonetici)).status_code == 200
    await _gonderildi_say()
    assert (await istemci.post(f"/api/oturumlar/{ot.id}/iptal", headers=yonetici)).status_code == 200
    assert await planlar() == []
    iptal = await bildirimler("telafi_iptal_edildi")
    assert len(iptal) == 2 and all(b.durum == BildirimDurum.bekliyor for b in iptal)
    assert await bildirimler("ek_ders_iptal_edildi") == []


async def test_ders_iptali_bekleyen_planlandi_bildirimi_duser(istemci, yonetici):
    ba, a1, a2, b1, o, kul_id, kisi_id = await bildirimli(istemci, yonetici)
    ot = await oturum_olustur(a2, gun(2))
    assert (await istemci.post(ek_url(ot), json=pl(o), headers=yonetici)).status_code == 200
    assert (await istemci.post(f"/api/oturumlar/{ot.id}/iptal", headers=yonetici)).status_code == 200
    assert all(b.durum == BildirimDurum.iptal for b in await bildirimler())


async def test_uyelik_plandan_ustundur_listede_uye(istemci, yonetici):
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    o = await ek_ogrenci(istemci, yonetici, a1)
    ot = await oturum_olustur(a2, gun(2))
    await kaydet(TelafiPlani(oturum_id=ot.id, ogrenci_id=o.id, tur=KatilimTuru.ek_ders))
    await uye_yap(o, a2)  # üyelik sonradan eklendi, plan satırı kalmış olsa bile
    y = (await istemci.get(f"/api/oturumlar/{ot.id}", headers=yonetici)).json()
    assert [(x["telafi_mi"], x["ek_ders_mi"]) for x in y["ogrenciler"]] == [(False, False)]


async def test_gruba_eklenince_gelecek_planlar_kalkar(istemci, yonetici):
    a1 = await grup_olustur("A1")
    a2 = await grup_olustur("A2")
    o = await ek_ogrenci(istemci, yonetici, a1, telafi=1)
    ileri = await oturum_olustur(a2, gun(2))
    ileri2 = await oturum_olustur(a2, gun(3))
    diger = await oturum_olustur(a1, gun(4))
    digergrup = await grup_olustur("A3")
    baska = await oturum_olustur(digergrup, gun(2))
    gecmis = await oturum_olustur(a2, gun(-2))
    assert (await istemci.post(plan_url(ileri), json=pl(o), headers=yonetici)).status_code == 200
    assert (await istemci.post(ek_url(ileri2), json=pl(o), headers=yonetici)).status_code == 200
    assert (await istemci.post(ek_url(baska), json=pl(o), headers=yonetici)).status_code == 200
    await kaydet(TelafiPlani(oturum_id=gecmis.id, ogrenci_id=o.id, tur=KatilimTuru.ek_ders))
    y = await istemci.post(f"/api/gruplar/{a2.id}/ogrenciler", json={"ogrenci_id": str(o.id)}, headers=yonetici)
    assert y.status_code == 200, y.text
    kalan = {p.oturum_id for p in await planlar()}
    assert kalan == {baska.id, gecmis.id}  # yalnız bu grubun gelecek planları kalktı
    async with SessionLocal() as s:
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "grup_uyeligi_planlari_kaldirdi"))).scalar_one()
    assert {x["oturum_id"] for x in k.detay["oturumlar"]} == {str(ileri.id), str(ileri2.id)}
    # Telafi hakkı serbest: telafi planı kalktı, tek hak yeniden kullanılabilir.
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 1
    assert diger


async def test_ders_plani_tercihi_ayri_ve_varsayilan_acik(istemci, yonetici):
    from tests.test_bildirim import giris as bgiris  # noqa: F401
    ba, a1, a2, b1, o, kul_id, kisi_id = await bildirimli(istemci, yonetici)
    from app.models import BildirimTercihi
    # ders_hakki kapalı olsa da plan bildirimi gider; ders_plani kapalıysa gitmez.
    async with SessionLocal() as s:
        s.add(BildirimTercihi(kullanici_id=kul_id, ders_hakki=False))
        await s.commit()
    ot = await oturum_olustur(a2, gun(2))
    assert (await istemci.post(ek_url(ot), json=pl(o), headers=ba)).status_code == 200
    assert len(await bildirimler("ek_ders_planlandi")) == 2
    async with SessionLocal() as s:
        t = await s.get(BildirimTercihi, kul_id)
        t.ders_hakki, t.ders_plani = True, False
        await s.commit()
    ot2 = await oturum_olustur(a2, gun(3))
    assert (await istemci.post(ek_url(ot2), json=pl(o), headers=ba)).status_code == 200
    assert len(await bildirimler("ek_ders_planlandi")) == 2
