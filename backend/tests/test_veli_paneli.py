"""Veli / reşit öğrenci paneli: yalnız kendi çocukları, yetki sınırları, profil."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    DenetimKaydi,
    DersHakkiHareketi,
    HareketTuru,
    IletisimKisisi,
    IletisimRolu,
    Kullanici,
    Odeme,
    OdemeYontemi,
    OgrenciPaketi,
    OgrenciPaketiDurum,
    Ogrenci,
    OturumDurum,
    Paket,
    PaketTuru,
    Rol,
    Sayac,
    TelafiPlani,
)
from tests.conftest import SIFRE, kullanici_olustur
from tests.test_yoklama import BUGUN, grup_olustur, kaydet, oturum_olustur, uye_yap

TELEFON = "+905551112233"


async def veli_ve_cocuk(giris="+905551112233", rol=Rol.veli, ad="Ali", soyad="Veli"):
    """Hesabı bağlı bir öğrenci; (baslik değil) kullanıcı ve öğrenci döner."""
    k = await kullanici_olustur(giris, rol)
    async with SessionLocal() as s:
        o = Ogrenci(ad=ad, soyad=soyad, dogum_tarihi=date(2015, 5, 10), kullanici_id=k.id if rol == Rol.ogrenci else None)
        s.add(o)
        await s.flush()
        s.add(
            IletisimKisisi(
                ogrenci_id=o.id, rol=IletisimRolu.kendisi if rol == Rol.ogrenci else IletisimRolu.anne,
                ad_soyad="Anne Veli", telefon=TELEFON, kullanici_id=k.id, birincil=True,
            )
        )
        await s.commit()
    return k, o


async def baslik(istemci, giris="+905551112233"):
    y = await istemci.post("/api/auth/login", json={"giris": giris, "sifre": SIFRE})
    assert y.status_code == 200, y.text
    return {"Authorization": f"Bearer {y.json()['access_token']}"}


async def paket_ata(ogrenci, durum=OgrenciPaketiDurum.odendi, odeme=True):
    async with SessionLocal() as s:
        p = Paket(ad="Aylık 8 ders", tur=PaketTuru.aylik, ders_sayisi=8, sure_ay=1, varsayilan_fiyat=Decimal("3400"))
        s.add(p)
        await s.flush()
        op = OgrenciPaketi(
            ogrenci_id=ogrenci.id, paket_id=p.id, ders_sayisi=8, liste_fiyati=Decimal("3400"),
            uygulanan_fiyat=Decimal("3400"), durum=durum,
        )
        s.add(op)
        await s.flush()
        if odeme:
            s.add(Odeme(ogrenci_paketi_id=op.id, tutar=Decimal("3400"), yontem=OdemeYontemi.nakit))
        await s.commit()
        return op


async def test_yetki(istemci):
    k, o = await veli_ve_cocuk()
    yol = [
        "/api/benim/cocuklar", f"/api/benim/cocuklar/{o.id}", f"/api/benim/cocuklar/{o.id}/foto", "/api/benim/profil",
    ]
    for u in yol:
        assert (await istemci.get(u)).status_code == 401
    for rol, eposta in ((Rol.admin, "y@kulup.com"), (Rol.antrenor, "a@kulup.com")):
        await kullanici_olustur(eposta, rol)
        y = await istemci.post("/api/auth/login", json={"giris": eposta, "sifre": SIFRE})
        b = {"Authorization": f"Bearer {y.json()['access_token']}"}
        for u in yol:
            assert (await istemci.get(u, headers=b)).status_code == 403


async def test_yalniz_kendi_cocuklari(istemci):
    k, ali = await veli_ve_cocuk()
    # Başka velinin çocuğu ve hiçbir hesaba bağlı olmayan çocuk.
    await veli_ve_cocuk("+905559998877", ad="Baska")
    async with SessionLocal() as s:
        yabanci = Ogrenci(ad="Yabanci", soyad="Kimse", dogum_tarihi=date(2014, 1, 1))
        s.add(yabanci)
        await s.commit()
    b = await baslik(istemci)
    liste = (await istemci.get("/api/benim/cocuklar", headers=b)).json()
    assert [c["ad"] for c in liste] == ["Ali"]
    assert (await istemci.get(f"/api/benim/cocuklar/{ali.id}", headers=b)).status_code == 200
    # Başkasının çocuğu ve olmayan kimlik aynı 404'ü verir.
    for oid in (yabanci.id, uuid.uuid4()):
        assert (await istemci.get(f"/api/benim/cocuklar/{oid}", headers=b)).status_code == 404


async def test_kardes_ayni_hesapta_iki_cocuk(istemci):
    k, ali = await veli_ve_cocuk()
    async with SessionLocal() as s:
        ayse = Ogrenci(ad="Ayse", soyad="Veli", dogum_tarihi=date(2016, 2, 2))
        s.add(ayse)
        await s.flush()
        s.add(IletisimKisisi(ogrenci_id=ayse.id, rol=IletisimRolu.anne, ad_soyad="Anne Veli", telefon=TELEFON,
                             kullanici_id=k.id, birincil=True))
        await s.commit()
    b = await baslik(istemci)
    assert [c["ad"] for c in (await istemci.get("/api/benim/cocuklar", headers=b)).json()] == ["Ali", "Ayse"]


async def test_resit_ogrenci_kendini_gorur(istemci):
    k, o = await veli_ve_cocuk("ogrenci@kulup.com", Rol.ogrenci, ad="Kendi")
    await veli_ve_cocuk("+905550001122", ad="Baska")
    b = await baslik(istemci, "ogrenci@kulup.com")
    assert [c["id"] for c in (await istemci.get("/api/benim/cocuklar", headers=b)).json()] == [str(o.id)]


async def test_sentetik_ogrenci_gorunmez(istemci):
    k, o = await veli_ve_cocuk()
    async with SessionLocal() as s:
        (await s.get(Ogrenci, o.id)).sentetik = True
        await s.commit()
    b = await baslik(istemci)
    assert (await istemci.get("/api/benim/cocuklar", headers=b)).json() == []
    assert (await istemci.get(f"/api/benim/cocuklar/{o.id}", headers=b)).status_code == 404


async def test_ozet_bakiye_siradaki_ders_ve_bekleyen_odeme(istemci):
    k, o = await veli_ve_cocuk()
    g = await grup_olustur("U10")
    await uye_yap(o, g)
    gecmis = await oturum_olustur(g, tarih=BUGUN - timedelta(days=2))
    yarin = await oturum_olustur(g, tarih=BUGUN + timedelta(days=1))
    await oturum_olustur(g, tarih=BUGUN + timedelta(days=3), durum=OturumDurum.iptal)
    await paket_ata(o, OgrenciPaketiDurum.odeme_bekliyor, odeme=False)
    await kaydet(DersHakkiHareketi(ogrenci_id=o.id, sayac=Sayac.telafi, miktar=2, tur=HareketTuru.manuel_duzeltme, neden="Deneme"))
    b = await baslik(istemci)
    c = (await istemci.get("/api/benim/cocuklar", headers=b)).json()[0]
    assert c["ders_hakki"] == {"normal": 0, "telafi": 2, "kullanilabilir_telafi": 2}
    assert c["gruplar"] == [{"id": str(g.id), "ad": "U10"}]
    assert c["siradaki_ders"]["oturum_id"] == str(yarin.id) and c["siradaki_ders"]["telafi_mi"] is False
    assert c["odeme_bekleyen"] == 1 and c["durum"] == "aktif"
    d = (await istemci.get(f"/api/benim/cocuklar/{o.id}", headers=b)).json()
    assert [x["oturum_id"] for x in d["yaklasan_dersler"]] == [str(yarin.id)]
    assert [x["oturum_id"] for x in d["gecmis_dersler"]] == [str(gecmis.id)]
    assert len(d["program"]) == 1 and d["program"][0]["gun"] == 1 and d["program"][0]["grup_ad"] == "U10"


async def test_telafi_dersi_yaklasan_listede_isaretli(istemci):
    k, o = await veli_ve_cocuk()
    diger = await grup_olustur("DIGER")
    ot = await oturum_olustur(diger, tarih=BUGUN + timedelta(days=2))
    await kaydet(TelafiPlani(oturum_id=ot.id, ogrenci_id=o.id))
    b = await baslik(istemci)
    d = (await istemci.get(f"/api/benim/cocuklar/{o.id}", headers=b)).json()
    assert [(x["oturum_id"], x["telafi_mi"]) for x in d["yaklasan_dersler"]] == [(str(ot.id), True)]
    assert d["program"] == []


async def test_paketler_ve_odemeler_ic_notsuz(istemci):
    k, o = await veli_ve_cocuk()
    op = await paket_ata(o)
    iptal = await paket_ata(o, OgrenciPaketiDurum.iptal, odeme=False)
    b = await baslik(istemci)
    d = (await istemci.get(f"/api/benim/cocuklar/{o.id}", headers=b)).json()
    assert [p["id"] for p in d["paketler"]] == [str(op.id)]  # iptal edilen paket gösterilmez
    p = d["paketler"][0]
    assert p["toplam_odenen"] == "3400.00" and p["uygulanan_fiyat"] == "3400.00" and p["durum"] == "odendi"
    assert set(p["odemeler"][0]) == {"tarih", "tutar", "yontem", "iptal"}
    assert o.id and iptal.id


async def test_hareketler_neden_ve_kullanici_icermez(istemci):
    k, o = await veli_ve_cocuk()
    await kaydet(DersHakkiHareketi(ogrenci_id=o.id, sayac=Sayac.normal, miktar=1, tur=HareketTuru.manuel_duzeltme,
                                   neden="Yönetici notu: gizli"))
    b = await baslik(istemci)
    d = (await istemci.get(f"/api/benim/cocuklar/{o.id}", headers=b)).json()
    assert set(d["hareketler"][0]) == {"zaman", "sayac", "miktar", "tur"}
    assert "gizli" not in (await istemci.get(f"/api/benim/cocuklar/{o.id}", headers=b)).text


async def test_foto_yok_404_ve_baskasinin_fotosu_404(istemci):
    k, o = await veli_ve_cocuk()
    k2, o2 = await veli_ve_cocuk("+905559998877", ad="Baska")
    b = await baslik(istemci)
    assert (await istemci.get(f"/api/benim/cocuklar/{o.id}/foto", headers=b)).status_code == 404
    assert (await istemci.get(f"/api/benim/cocuklar/{o2.id}/foto", headers=b)).status_code == 404


async def test_profil_getir_ve_guncelle(istemci):
    k, o = await veli_ve_cocuk()
    b = await baslik(istemci)
    p = (await istemci.get("/api/benim/profil", headers=b)).json()
    assert p == {"giris": TELEFON, "rol": "veli", "ad_soyad": "Anne Veli", "telefon": TELEFON}
    y = await istemci.patch("/api/benim/profil", json={"ad_soyad": " Yeni Ad ", "telefon": "0532 111 22 44"}, headers=b)
    assert y.status_code == 200, y.text
    assert y.json()["ad_soyad"] == "Yeni Ad" and y.json()["telefon"] == "+905321112244"
    assert y.json()["giris"] == TELEFON  # giriş bilgisi değişmez
    async with SessionLocal() as s:
        kisi = (await s.execute(select(IletisimKisisi))).scalar_one()
        assert kisi.ad_soyad == "Yeni Ad" and kisi.telefon == "+905321112244"
        assert (await s.get(Kullanici, k.id)).ad_soyad == "Yeni Ad"
        log = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "profil_guncellendi"))).scalar_one()
        assert log.kullanici_id == k.id and log.detay is None


async def test_profil_dogrulama(istemci):
    await veli_ve_cocuk()
    b = await baslik(istemci)
    for govde in (
        {"ad_soyad": "Ad", "telefon": "123"},
        {"ad_soyad": "  ", "telefon": "05321112244"},
        {"ad_soyad": "Ad", "telefon": "05321112244", "rol": "admin"},
    ):
        assert (await istemci.patch("/api/benim/profil", json=govde, headers=b)).status_code == 422


async def test_resit_ogrenci_profili_ogrenci_telefonunu_da_gunceller(istemci):
    k, o = await veli_ve_cocuk("ogrenci@kulup.com", Rol.ogrenci, ad="Kendi")
    b = await baslik(istemci, "ogrenci@kulup.com")
    y = await istemci.patch("/api/benim/profil", json={"ad_soyad": "Kendi Ad", "telefon": "05321112244"}, headers=b)
    assert y.status_code == 200
    async with SessionLocal() as s:
        assert (await s.get(Ogrenci, o.id)).telefon == "+905321112244"
