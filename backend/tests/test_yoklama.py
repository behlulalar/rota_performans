"""Ders oturumu, takvim, yoklama ve ders hakkı uç noktaları (HTTP üzerinden)."""
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Antrenor,
    DenetimKaydi,
    DersOturumu,
    Grup,
    GrupProgrami,
    Kullanici,
    Ogrenci,
    OgrenciGrup,
    OturumDurum,
    Rol,
    TelafiPlani,
    Yoklama,
)
from app.oturumlar import bugun
from tests.conftest import SIFRE, kullanici_olustur

BUGUN = bugun()  # İstanbul saatine göre


async def giris(istemci, eposta, rol):
    await kullanici_olustur(eposta, rol)
    yanit = await istemci.post("/api/auth/login", json={"giris": eposta, "sifre": SIFRE})
    return {"Authorization": f"Bearer {yanit.json()['access_token']}"}


@pytest.fixture
async def yonetici(istemci):
    return await giris(istemci, "yonetici@kulup.com", Rol.admin)


async def kaydet(*nesneler):
    async with SessionLocal() as s:
        s.add_all(nesneler)
        await s.commit()


async def antrenor_hesabi(istemci, eposta, ad, aktif=True):
    baslik = await giris(istemci, eposta, Rol.antrenor)
    async with SessionLocal() as s:
        k = (await s.execute(select(Kullanici).where(Kullanici.giris == eposta))).scalar_one()
        a = Antrenor(kullanici_id=k.id, ad_soyad=ad, aktif=aktif)
        s.add(a)
        await s.commit()
    return baslik, a


async def grup_olustur(ad="U10", antrenor=None, aktif=True, program=((1, time(17), time(18, 30)),)):
    g = Grup(ad=ad, kontenjan=10, antrenor_id=antrenor.id if antrenor else None, aktif=aktif)
    await kaydet(g)
    await kaydet(*[GrupProgrami(grup_id=g.id, gun=gun, baslangic=b, bitis=e) for gun, b, e in program])
    return g


# Varsayılan 00:00: antrenörün yoklaması günün her saatinde açık olsun (15 dk kuralı testleri ayrıca saati ayarlar).
async def oturum_olustur(grup, tarih=None, antrenor=None, durum=OturumDurum.planli, baslangic=time(0)):
    ot = DersOturumu(
        grup_id=grup.id, tarih=tarih or BUGUN, baslangic=baslangic, bitis=time(baslangic.hour + 1, 30),
        antrenor_id=antrenor.id if antrenor else None, durum=durum,
    )
    await kaydet(ot)
    return ot


async def ogrenci_olustur(ad="Ali", soyad="Yilmaz"):
    o = Ogrenci(ad=ad, soyad=soyad, dogum_tarihi=date(2015, 5, 10))
    await kaydet(o)
    return o


async def uye_yap(ogrenci, grup, baslangic=date(2020, 1, 1), bitis=None):
    await kaydet(OgrenciGrup(ogrenci_id=ogrenci.id, grup_id=grup.id, baslangic=baslangic, bitis=bitis))


def govde(*cift):
    return [{"ogrenci_id": str(o.id), "durum": d} for o, d in cift]


def sorgu(bas=None, bit=None):
    return f"/api/takvim?baslangic={bas or BUGUN}&bitis={bit or BUGUN}"


# ---------- oturum üretimi ----------


async def test_uretim_dogru_gunler_ve_tekrarda_sifir(istemci, yonetici):
    # 2026-11-02 pazartesi; pazartesi + çarşamba dersi.
    await grup_olustur(program=((1, time(17), time(18, 30)), (3, time(10), time(11))))
    g = {"baslangic": "2026-11-02", "bitis": "2026-11-15"}
    yanit = await istemci.post("/api/oturumlar/uret", json=g, headers=yonetici)
    assert yanit.status_code == 200 and yanit.json() == {"olusturulan": 4}
    liste = (await istemci.get(sorgu("2026-11-01", "2026-11-30"), headers=yonetici)).json()
    assert [o["tarih"] for o in liste] == ["2026-11-02", "2026-11-04", "2026-11-09", "2026-11-11"]
    assert all(o["durum"] == "planli" and o["yoklama_alindi"] is False for o in liste)
    assert (await istemci.post("/api/oturumlar/uret", json=g, headers=yonetici)).json() == {"olusturulan": 0}
    uzun = await istemci.post(
        "/api/oturumlar/uret", json={"baslangic": "2026-11-02", "bitis": "2026-11-22"}, headers=yonetici
    )
    assert uzun.json() == {"olusturulan": 2}


async def test_uretim_pasif_grubu_atlar(istemci, yonetici):
    await grup_olustur(aktif=False)
    yanit = await istemci.post(
        "/api/oturumlar/uret", json={"baslangic": "2026-11-02", "bitis": "2026-11-15"}, headers=yonetici
    )
    assert yanit.json() == {"olusturulan": 0}


async def test_uretim_aralik_siniri_ve_yetki(istemci, yonetici):
    await grup_olustur()
    bas = date(2026, 11, 2)
    ok = await istemci.post(
        "/api/oturumlar/uret", json={"baslangic": str(bas), "bitis": str(bas + timedelta(days=61))}, headers=yonetici
    )
    assert ok.status_code == 200
    uzun = await istemci.post(
        "/api/oturumlar/uret", json={"baslangic": str(bas), "bitis": str(bas + timedelta(days=62))}, headers=yonetici
    )
    assert uzun.status_code == 422
    ters = await istemci.post(
        "/api/oturumlar/uret", json={"baslangic": "2026-11-05", "bitis": "2026-11-01"}, headers=yonetici
    )
    assert ters.status_code == 422
    kisa = {"baslangic": "2026-11-02", "bitis": "2026-11-03"}
    ba, _ = await antrenor_hesabi(istemci, "hoca@kulup.com", "Hoca")
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    assert (await istemci.post("/api/oturumlar/uret", json=kisa, headers=ba)).status_code == 403
    assert (await istemci.post("/api/oturumlar/uret", json=kisa, headers=veli)).status_code == 403
    assert (await istemci.post("/api/oturumlar/uret", json=kisa)).status_code == 401


# ---------- takvim ----------


async def test_takvim_antrenor_kendi_oturumlari_yerine_bakan_ve_admin_filtresi(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "a@kulup.com", "Hoca A")
    bb, b = await antrenor_hesabi(istemci, "b@kulup.com", "Hoca B")
    ga, gb, gc = await grup_olustur("GA", a), await grup_olustur("GB", b), await grup_olustur("GC", None)
    o_a = await oturum_olustur(ga)
    o_b = await oturum_olustur(gb)
    o_c_a = await oturum_olustur(gc, antrenor=a)  # A yerine bakıyor
    o_a_b = await oturum_olustur(ga, antrenor=b, baslangic=time(19))  # grubu A'nın, B bakıyor

    gor_a = {o["id"]: o for o in (await istemci.get(sorgu(), headers=ba)).json()}
    assert set(gor_a) == {str(o_a.id), str(o_c_a.id)}
    assert str(o_a_b.id) not in gor_a  # asıl antrenör yerine bakılan oturumu görmez
    assert gor_a[str(o_c_a.id)]["antrenor"] == {"id": str(a.id), "ad_soyad": "Hoca A"}
    # antrenor_id parametresi antrenörde yok sayılır.
    yok = (await istemci.get(sorgu() + f"&antrenor_id={b.id}", headers=ba)).json()
    assert {o["id"] for o in yok} == set(gor_a)
    gor_b = {o["id"] for o in (await istemci.get(sorgu(), headers=bb)).json()}
    assert gor_b == {str(o_b.id), str(o_a_b.id)}

    hepsi = (await istemci.get(sorgu(), headers=yonetici)).json()
    assert len(hepsi) == 4
    suz = (await istemci.get(sorgu() + f"&antrenor_id={a.id}", headers=yonetici)).json()
    assert {o["id"] for o in suz} == set(gor_a)


async def test_takvim_antrenorsuz_oturum_alani_bos(istemci, yonetici):
    await oturum_olustur(await grup_olustur("GC", None))
    assert (await istemci.get(sorgu(), headers=yonetici)).json()[0]["antrenor"] is None


async def test_takvim_veli_pasif_antrenor_ve_kayitsiz_403(istemci, yonetici):
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    assert (await istemci.get(sorgu(), headers=veli)).status_code == 403
    assert (await istemci.get(sorgu())).status_code == 401
    pasif, _ = await antrenor_hesabi(istemci, "pasif@kulup.com", "Pasif", aktif=False)
    assert (await istemci.get(sorgu(), headers=pasif)).status_code == 403
    kayitsiz = await giris(istemci, "kayitsiz@kulup.com", Rol.antrenor)
    assert (await istemci.get(sorgu(), headers=kayitsiz)).status_code == 403


async def test_takvim_aralik_siniri(istemci, yonetici):
    bas = date(2026, 11, 1)
    assert (await istemci.get(sorgu(bas, bas + timedelta(days=61)), headers=yonetici)).status_code == 200
    assert (await istemci.get(sorgu(bas, bas + timedelta(days=62)), headers=yonetici)).status_code == 422
    assert (await istemci.get(sorgu(bas + timedelta(days=1), bas), headers=yonetici)).status_code == 422


async def test_takvim_ogrenci_sayisi_ve_yoklama_alindi(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "a@kulup.com", "Hoca A")
    g = await grup_olustur("GA", a)
    ot = await oturum_olustur(g)
    boş_ot = await oturum_olustur(g, tarih=BUGUN + timedelta(days=1))
    uye, ayrilmis, gelecek, telafici = [await ogrenci_olustur(f"O{i}", "S") for i in range(4)]
    await uye_yap(uye, g)
    await uye_yap(ayrilmis, g, bitis=BUGUN - timedelta(days=1))
    await uye_yap(gelecek, g, baslangic=BUGUN + timedelta(days=1))
    await kaydet(TelafiPlani(oturum_id=ot.id, ogrenci_id=telafici.id))
    liste = (await istemci.get(sorgu(BUGUN, BUGUN + timedelta(days=1)), headers=ba)).json()
    bugunku, yarinki = liste
    assert bugunku["id"] == str(ot.id) and bugunku["ogrenci_sayisi"] == 2  # üye + telafi
    assert yarinki["id"] == str(boş_ot.id) and yarinki["ogrenci_sayisi"] == 2  # yarın katılan da var
    assert bugunku["yoklama_alindi"] is False
    await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((uye, "geldi")), headers=ba)
    liste = (await istemci.get(sorgu(), headers=ba)).json()
    assert liste[0]["yoklama_alindi"] is True


# ---------- oturum detayı ----------


async def test_detay_liste_uyelikler_telafi_ve_bakiye(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "a@kulup.com", "Hoca A")
    g, diger = await grup_olustur("GA", a), await grup_olustur("Diger")
    ot = await oturum_olustur(g)
    zeynep, ali = await ogrenci_olustur("Zeynep", "Kaya"), await ogrenci_olustur("Ali", "Kaya")
    ayrilmis, gelecek = await ogrenci_olustur("Ayrilmis", "Aa"), await ogrenci_olustur("Gelecek", "Bb")
    bitis_bugun, baska = await ogrenci_olustur("Bitis", "Cc"), await ogrenci_olustur("Baska", "Dd")
    telafici = await ogrenci_olustur("Telafi", "Aa")
    await uye_yap(zeynep, g)
    await uye_yap(ali, g)
    await uye_yap(ayrilmis, g, bitis=BUGUN - timedelta(days=1))
    await uye_yap(gelecek, g, baslangic=BUGUN + timedelta(days=1))
    await uye_yap(bitis_bugun, g, bitis=BUGUN)
    await uye_yap(baska, diger)
    await kaydet(TelafiPlani(oturum_id=ot.id, ogrenci_id=telafici.id))
    d = (await istemci.get(f"/api/oturumlar/{ot.id}", headers=ba)).json()
    assert [(o["soyad"], o["ad"], o["telafi_mi"]) for o in d["ogrenciler"]] == [
        ("Aa", "Telafi", True), ("Cc", "Bitis", False), ("Kaya", "Ali", False), ("Kaya", "Zeynep", False),
    ]
    assert all(
        o["yoklama"] is None and o["bakiye"] == {"normal": 0, "telafi": 0} and o["foto_var"] is False
        for o in d["ogrenciler"]
    )
    assert d["ogrenci_sayisi"] == 4 and d["yoklama_alindi"] is False
    assert d["grup"] == {"id": str(g.id), "ad": "GA"} and d["antrenor"]["id"] == str(a.id)


async def test_detay_baska_antrenor_veli_403_yonetici_gorur_olmayan_404(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "a@kulup.com", "Hoca A")
    bb, _ = await antrenor_hesabi(istemci, "b@kulup.com", "Hoca B")
    ot = await oturum_olustur(await grup_olustur("GA", a))
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    url = f"/api/oturumlar/{ot.id}"
    assert (await istemci.get(url, headers=ba)).status_code == 200
    assert (await istemci.get(url, headers=bb)).status_code == 403
    assert (await istemci.get(url, headers=veli)).status_code == 403
    assert (await istemci.get(url, headers=yonetici)).status_code == 200
    assert (await istemci.get(f"/api/oturumlar/{uuid.uuid4()}", headers=yonetici)).status_code == 404


# ---------- yoklama ----------


async def hazir(istemci):
    ba, a = await antrenor_hesabi(istemci, "a@kulup.com", "Hoca A")
    g = await grup_olustur("GA", a)
    ot = await oturum_olustur(g)
    o1, o2 = await ogrenci_olustur("Ali", "Yilmaz"), await ogrenci_olustur("Veli", "Zor")
    await uye_yap(o1, g)
    await uye_yap(o2, g)
    return ba, ot, o1, o2


async def test_yoklama_gelecek_tarih_422(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "a@kulup.com", "Hoca A")
    g = await grup_olustur("GA", a)
    o = await ogrenci_olustur()
    await uye_yap(o, g)
    yarin = await oturum_olustur(g, tarih=BUGUN + timedelta(days=1))
    yanit = await istemci.put(f"/api/oturumlar/{yarin.id}/yoklama", json=govde((o, "geldi")), headers=ba)
    assert yanit.status_code == 422 and yanit.json()["detail"] == "Gelecek tarihli derse yoklama alınamaz"
    dun = await oturum_olustur(g, tarih=BUGUN - timedelta(days=1))
    assert (await istemci.put(f"/api/oturumlar/{dun.id}/yoklama", json=govde((o, "geldi")), headers=ba)).status_code == 200


async def test_yoklama_iptal_oturum_422(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "a@kulup.com", "Hoca A")
    g = await grup_olustur("GA", a)
    o = await ogrenci_olustur()
    await uye_yap(o, g)
    ot = await oturum_olustur(g, durum=OturumDurum.iptal)
    assert (await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o, "geldi")), headers=ba)).status_code == 422


async def test_yoklama_listede_olmayan_tekrar_eden_ve_gecersiz_422_hicbir_sey_yazilmaz(istemci, yonetici):
    ba, ot, o1, o2 = await hazir(istemci)
    yabanci = await ogrenci_olustur("Yabanci", "Kisi")
    url = f"/api/oturumlar/{ot.id}/yoklama"
    assert (await istemci.put(url, json=govde((o1, "geldi"), (yabanci, "geldi")), headers=ba)).status_code == 422
    assert (await istemci.put(url, json=govde((o1, "geldi"), (o1, "gelmedi")), headers=ba)).status_code == 422
    assert (await istemci.put(url, json=[{"ogrenci_id": str(o1.id), "durum": "izinli"}], headers=ba)).status_code == 422
    d = (await istemci.get(f"/api/oturumlar/{ot.id}", headers=ba)).json()
    assert d["yoklama_alindi"] is False and all(o["yoklama"] is None for o in d["ogrenciler"])
    assert (await istemci.get(f"/api/ogrenciler/{o1.id}/ders-hakki", headers=yonetici)).json()["hareketler"] == []


async def test_yoklama_baska_antrenor_ve_veli_403(istemci, yonetici):
    ba, ot, o1, o2 = await hazir(istemci)
    bb, _ = await antrenor_hesabi(istemci, "b@kulup.com", "Hoca B")
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    url = f"/api/oturumlar/{ot.id}/yoklama"
    assert (await istemci.put(url, json=govde((o1, "geldi")), headers=bb)).status_code == 403
    assert (await istemci.put(url, json=govde((o1, "geldi")), headers=veli)).status_code == 403
    assert (await istemci.put(url, json=govde((o1, "geldi")))).status_code == 401
    assert (await istemci.get(f"/api/oturumlar/{ot.id}", headers=ba)).json()["yoklama_alindi"] is False


async def test_geldi_hemen_normal_eksi_bir_gelmedi_hemen_hareket_yok(istemci, yonetici):
    ba, ot, o1, o2 = await hazir(istemci)
    url = f"/api/oturumlar/{ot.id}/yoklama"
    yanit = await istemci.put(url, json=govde((o1, "geldi"), (o2, "gelmedi")), headers=ba)
    assert yanit.status_code == 200, yanit.text
    d = yanit.json()
    assert d["yoklama_alindi"] is True
    durum = {o["ad"]: (o["yoklama"], o["bakiye"]) for o in d["ogrenciler"]}
    assert durum["Ali"] == ("geldi", {"normal": -1, "telafi": 0})
    assert durum["Veli"] == ("gelmedi", {"normal": 0, "telafi": 0})
    ders1 = (await istemci.get(f"/api/ogrenciler/{o1.id}/ders-hakki", headers=yonetici)).json()
    assert (ders1["normal"], ders1["telafi"]) == (-1, 0)
    ders2 = (await istemci.get(f"/api/ogrenciler/{o2.id}/ders-hakki", headers=yonetici)).json()
    assert ders2 == {"normal": 0, "telafi": 0, "hareketler": []}
    # Aynı isteğin tekrarı yeni hareket yazmaz.
    await istemci.put(url, json=govde((o1, "geldi"), (o2, "gelmedi")), headers=ba)
    assert len((await istemci.get(f"/api/ogrenciler/{o1.id}/ders-hakki", headers=yonetici)).json()["hareketler"]) == 1


async def test_admin_yoklama_alabilir_ve_duzeltebilir_kismi_liste(istemci, yonetici):
    ba, ot, o1, o2 = await hazir(istemci)
    url = f"/api/oturumlar/{ot.id}/yoklama"
    assert (await istemci.put(url, json=govde((o1, "geldi")), headers=yonetici)).status_code == 200
    yanit = await istemci.put(url, json=govde((o1, "gelmedi")), headers=yonetici)
    assert yanit.status_code == 200
    # Göndermediğimiz öğrenci için yoklama oluşmaz; düzeltilenin bakiyesi eski haline döner.
    assert {o["ad"]: (o["yoklama"], o["bakiye"]) for o in yanit.json()["ogrenciler"]} == {
        "Ali": ("gelmedi", {"normal": 0, "telafi": 0}),
        "Veli": (None, {"normal": 0, "telafi": 0}),
    }


async def test_telafi_ogrencisi_telafi_hakkindan_duser(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "a@kulup.com", "Hoca A")
    ot = await oturum_olustur(await grup_olustur("GA", a))
    t1, t2 = await ogrenci_olustur("Telafi", "Bir"), await ogrenci_olustur("Telafi", "Iki")
    await kaydet(TelafiPlani(oturum_id=ot.id, ogrenci_id=t1.id), TelafiPlani(oturum_id=ot.id, ogrenci_id=t2.id))
    yanit = await istemci.put(
        f"/api/oturumlar/{ot.id}/yoklama", json=govde((t1, "geldi"), (t2, "gelmedi")), headers=ba
    )
    assert {o["soyad"]: o["bakiye"] for o in yanit.json()["ogrenciler"]} == {
        "Bir": {"normal": 0, "telafi": -1}, "Iki": {"normal": 0, "telafi": 0},
    }


async def test_denetim_kaydi_yoklama_alindi_kisisel_veri_yok(istemci, yonetici):
    ba, ot, o1, o2 = await hazir(istemci)
    await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o1, "geldi"), (o2, "gelmedi")), headers=ba)
    async with SessionLocal() as s:
        kayit = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "yoklama_alindi"))).scalar_one()
    assert kayit.hedef_tur == "ders_oturumu" and kayit.hedef_id == str(ot.id)
    assert kayit.detay == {"toplam": 2, "geldi": 1, "gelmedi": 1}
    metin = str(kayit.detay) + str(kayit.hedef_id)
    for kisisel in ("Ali", "Yilmaz", "Veli", str(o1.id), str(o2.id)):
        assert kisisel not in metin


# ---------- ders hakkı ucu ----------


async def test_ders_hakki_ucu_hareketler_iptal_satiri_oturumu_ve_yetki(istemci, yonetici):
    ba, ot, o1, o2 = await hazir(istemci)
    url = f"/api/oturumlar/{ot.id}/yoklama"
    await istemci.put(url, json=govde((o1, "geldi")), headers=ba)
    await istemci.put(url, json=govde((o1, "gelmedi")), headers=ba)
    ders = (await istemci.get(f"/api/ogrenciler/{o1.id}/ders-hakki", headers=yonetici)).json()
    assert (ders["normal"], ders["telafi"]) == (0, 0)
    assert [(h["tur"], h["sayac"], h["miktar"]) for h in ders["hareketler"]] == [
        ("iptal", "normal", 1), ("ders_kullanimi", "normal", -1),
    ]  # zaman azalan
    assert all(h["oturum"] == {"tarih": str(BUGUN), "grup_ad": "GA"} for h in ders["hareketler"])
    assert all({"id", "zaman", "sayac", "miktar", "tur", "neden", "oturum"} <= set(h) for h in ders["hareketler"])
    detay = (await istemci.get(f"/api/ogrenciler/{o1.id}", headers=yonetici)).json()
    assert detay["ders_hakki"] == {"normal": 0, "telafi": 0, "kullanilabilir_telafi": 0}
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    assert (await istemci.get(f"/api/ogrenciler/{o1.id}/ders-hakki", headers=ba)).status_code == 403
    assert (await istemci.get(f"/api/ogrenciler/{o1.id}/ders-hakki", headers=veli)).status_code == 403
    assert (await istemci.get(f"/api/ogrenciler/{uuid.uuid4()}/ders-hakki", headers=yonetici)).status_code == 404


# ---------- yoklama ders başlamadan 15 dakika önce açılır ----------


def _istanbul(saat: time) -> datetime:
    return datetime.combine(BUGUN, saat, tzinfo=ZoneInfo("Europe/Istanbul"))


async def _saat_ayarla(monkeypatch, an: datetime):
    import app.api.oturumlar as uc

    monkeypatch.setattr(uc, "simdi", lambda: an)


async def test_antrenor_ders_baslamadan_15_dakikadan_once_yoklama_alamaz(istemci, yonetici, monkeypatch):
    ba, a = await antrenor_hesabi(istemci, "a@kulup.com", "Hoca A")
    g = await grup_olustur("GA", a)
    o = await ogrenci_olustur()
    await uye_yap(o, g)
    ot = await oturum_olustur(g, baslangic=time(18))

    await _saat_ayarla(monkeypatch, _istanbul(time(17, 44, 59)))
    yanit = await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o, "geldi")), headers=ba)
    assert yanit.status_code == 422
    assert yanit.json()["detail"] == "Yoklama 17:45'te açılır (ders başlamadan 15 dakika önce)"
    async with SessionLocal() as s:
        assert (await s.execute(select(Yoklama))).first() is None

    await _saat_ayarla(monkeypatch, _istanbul(time(17, 45)))
    assert (await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o, "geldi")), headers=ba)).status_code == 200


async def test_yonetici_15_dakika_kuralina_tabi_degil(istemci, yonetici, monkeypatch):
    _, a = await antrenor_hesabi(istemci, "a@kulup.com", "Hoca A")
    g = await grup_olustur("GA", a)
    o = await ogrenci_olustur()
    await uye_yap(o, g)
    ot = await oturum_olustur(g, baslangic=time(18))
    await _saat_ayarla(monkeypatch, _istanbul(time(8)))
    assert (await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o, "geldi")), headers=yonetici)).status_code == 200
