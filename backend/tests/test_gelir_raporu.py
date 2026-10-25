from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    DenetimKaydi,
    Odeme,
    OdemeYontemi,
    Ogrenci,
    OgrenciPaketi,
    OgrenciPaketiDurum,
    Paket,
    PaketTuru,
    Rol,
)
from app.oturumlar import bugun
from tests.test_paketler import giris


@pytest.fixture
async def yonetici(istemci):
    return await giris(istemci, "yonetici@kulup.com", Rol.admin)


async def paket_ekle(ad="Aylık 8 Ders", fiyat="3400.00"):
    async with SessionLocal() as s:
        p = Paket(ad=ad, tur=PaketTuru.aylik, ders_sayisi=8, sure_ay=1, varsayilan_fiyat=Decimal(fiyat))
        s.add(p)
        await s.commit()
        return p.id


async def ogrenci_ekle(ad="Deneme", soyad="Öğrenci", sentetik=False):
    async with SessionLocal() as s:
        o = Ogrenci(ad=ad, soyad=soyad, dogum_tarihi=date(2015, 5, 10), sentetik=sentetik)
        s.add(o)
        await s.commit()
        return o.id


async def odeme_ekle(
    paket_id, tutar, tarih, yontem=OdemeYontemi.nakit, iptal=False, ogrenci_id=None, liste=None, ozel=False,
    sentetik=False, aciklama=None, ad="Deneme", soyad="Öğrenci",
):
    """Ödenmiş paket + tek ödeme satırı ekler."""
    tutar = Decimal(tutar)
    oid = ogrenci_id or await ogrenci_ekle(ad, soyad, sentetik)
    async with SessionLocal() as s:
        op = OgrenciPaketi(
            ogrenci_id=oid, paket_id=paket_id, ders_sayisi=8, liste_fiyati=Decimal(liste or tutar),
            uygulanan_fiyat=tutar, fiyat_ozel_mi=ozel,
            durum=OgrenciPaketiDurum.odeme_bekliyor if iptal else OgrenciPaketiDurum.odendi,
        )
        s.add(op)
        await s.flush()
        o = Odeme(
            ogrenci_paketi_id=op.id, tutar=tutar, tarih=tarih, yontem=yontem, aciklama=aciklama,
            iptal_zamani=datetime.now(timezone.utc) if iptal else None, iptal_nedeni="hata" if iptal else None,
        )
        s.add(o)
        await s.commit()
        return op.id


async def paket_satiri(paket_id, fiyat, durum, olusturma=None, ozel=False, liste=None, sentetik=False):
    oid = await ogrenci_ekle(sentetik=sentetik)
    async with SessionLocal() as s:
        op = OgrenciPaketi(
            ogrenci_id=oid, paket_id=paket_id, ders_sayisi=8, liste_fiyati=Decimal(liste or fiyat),
            uygulanan_fiyat=Decimal(fiyat), fiyat_ozel_mi=ozel, durum=durum,
        )
        if olusturma:
            op.olusturma = olusturma
        s.add(op)
        await s.commit()


def rapor(istemci, yonetici, yil=2026, ay=3):
    return istemci.get(f"/api/raporlar/gelir?yil={yil}&ay={ay}", headers=yonetici)


async def test_yetki(istemci, yonetici):
    antrenor = await giris(istemci, "hoca@kulup.com", Rol.antrenor)
    for yol in ("/api/raporlar/gelir", "/api/raporlar/gelir.csv"):
        assert (await istemci.get(yol, headers=antrenor)).status_code == 403
        assert (await istemci.get(yol)).status_code == 401


async def test_bos_donem(istemci, yonetici):
    r = await rapor(istemci, yonetici, 2026, 2)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["donem"] == {"yil": 2026, "ay": 2, "baslangic": "2026-02-01", "bitis": "2026-02-28"}
    assert j["ozet"] == {
        "toplam_tahsilat": "0.00", "odeme_adedi": 0, "ortalama_odeme": "0.00", "onceki_ay_tahsilat": "0.00",
        "degisim_yuzde": None, "iptal_edilen_tutar": "0.00", "iptal_adedi": 0, "indirim_toplami": "0.00",
        "ucretsiz_paket_adedi": 0,
    }
    assert j["bekleyen"] == {"adet": 0, "tutar": "0.00", "gecikmis_adet": 0, "gecikmis_tutar": "0.00"}
    assert j["yontem_dagilimi"] == [] and j["paket_dagilimi"] == []
    assert len(j["gunluk"]) == 28 and all(g["tutar"] == "0.00" and g["adet"] == 0 for g in j["gunluk"])
    assert j["gunluk"][0]["tarih"] == "2026-02-01" and j["gunluk"][-1]["tarih"] == "2026-02-28"
    assert len(j["aylik_seri"]) == 12


async def test_varsayilan_donem_icinde_bulunulan_ay(istemci, yonetici):
    j = (await istemci.get("/api/raporlar/gelir", headers=yonetici)).json()
    t = bugun()
    assert (j["donem"]["yil"], j["donem"]["ay"]) == (t.year, t.month)
    assert j["aylik_seri"][-1]["yil"] == t.year and j["aylik_seri"][-1]["ay"] == t.month


async def test_varsayilan_donem_kulup_saat_dilimi(istemci, yonetici, monkeypatch):
    # 31 Ocak 22:00 UTC = 1 Şubat 01:00 İstanbul: rapor Şubat olmalı.
    from app import oturumlar

    sabit = datetime(2026, 1, 31, 22, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(oturumlar, "simdi", lambda: sabit)
    j = (await istemci.get("/api/raporlar/gelir", headers=yonetici)).json()
    assert (j["donem"]["yil"], j["donem"]["ay"]) == (2026, 2)


async def test_dagilimlar_iptal_ve_sentetik(istemci, yonetici):
    p1, p2 = await paket_ekle("Aylık 8 Ders"), await paket_ekle("3 Aylık", "9000.00")
    await odeme_ekle(p1, "3400", date(2026, 3, 1))
    await odeme_ekle(p1, "3400", date(2026, 3, 1), OdemeYontemi.havale_eft)
    await odeme_ekle(p2, "9000", date(2026, 3, 31), OdemeYontemi.havale_eft)
    await odeme_ekle(p1, "3400", date(2026, 3, 15), iptal=True)
    await odeme_ekle(p1, "100", date(2026, 3, 15), sentetik=True)  # hariç
    await odeme_ekle(p1, "3400", date(2026, 4, 1))  # dönem dışı
    await odeme_ekle(p1, "3400", date(2026, 2, 28))  # dönem dışı
    j = (await rapor(istemci, yonetici)).json()
    o = j["ozet"]
    assert o["toplam_tahsilat"] == "15800.00" and o["odeme_adedi"] == 3
    assert o["ortalama_odeme"] == "5266.67"
    assert o["iptal_edilen_tutar"] == "3400.00" and o["iptal_adedi"] == 1
    assert o["onceki_ay_tahsilat"] == "3400.00"
    assert o["degisim_yuzde"] == 364.71
    yd = {y["yontem"]: y for y in j["yontem_dagilimi"]}
    assert yd["nakit"]["tutar"] == "3400.00" and yd["nakit"]["adet"] == 1 and yd["nakit"]["yuzde"] == 21.52
    assert yd["havale_eft"]["tutar"] == "12400.00" and yd["havale_eft"]["adet"] == 2 and yd["havale_eft"]["yuzde"] == 78.48
    assert [(x["paket_adi"], x["tutar"], x["adet"]) for x in j["paket_dagilimi"]] == [
        ("3 Aylık", "9000.00", 1), ("Aylık 8 Ders", "6800.00", 2),
    ]
    g = {x["tarih"]: x for x in j["gunluk"]}
    assert len(g) == 31
    assert g["2026-03-01"]["tutar"] == "6800.00" and g["2026-03-01"]["adet"] == 2
    assert g["2026-03-31"]["tutar"] == "9000.00" and g["2026-03-15"]["adet"] == 0  # iptal sayılmaz
    assert "Öğrenci" not in str(j) and "Deneme" not in str(j)  # kişisel veri yok


async def test_degisim_yuzde_ve_sifira_bolme(istemci, yonetici):
    p = await paket_ekle()
    await odeme_ekle(p, "1000", date(2026, 2, 10))
    await odeme_ekle(p, "500", date(2026, 3, 10))
    assert (await rapor(istemci, yonetici, 2026, 3)).json()["ozet"]["degisim_yuzde"] == -50.0
    # Önceki ay (Şubat) 1000 iken Nisan'ın önceki ayı (Mart) 500; Mayıs'ın önceki ayı 0
    assert (await rapor(istemci, yonetici, 2026, 5)).json()["ozet"]["degisim_yuzde"] is None
    assert (await rapor(istemci, yonetici, 2026, 4)).json()["ozet"]["degisim_yuzde"] == -100.0


async def test_indirim_ve_ucretsiz_paket(istemci, yonetici):
    p = await paket_ekle()
    await odeme_ekle(p, "3000", date(2026, 3, 5), liste="3400", ozel=True)  # 400 indirim
    await odeme_ekle(p, "3400", date(2026, 3, 6))  # özel değil
    await odeme_ekle(p, "3000", date(2026, 3, 7), liste="3400", ozel=True, iptal=True)  # iptal: sayılmaz
    await odeme_ekle(p, "2000", date(2026, 4, 7), liste="3400", ozel=True)  # dönem dışı
    mart = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
    await paket_satiri(p, "0", OgrenciPaketiDurum.odendi, mart, ozel=True, liste="3400")  # ücretsiz
    await paket_satiri(p, "0", OgrenciPaketiDurum.odendi, mart, ozel=True, liste="3400", sentetik=True)
    await paket_satiri(p, "0", OgrenciPaketiDurum.odendi, datetime(2026, 4, 10, tzinfo=timezone.utc), ozel=True, liste="3400")
    o = (await rapor(istemci, yonetici)).json()["ozet"]
    assert o["indirim_toplami"] == "400.00" and o["ucretsiz_paket_adedi"] == 1


async def test_ucretsiz_paket_saat_dilimi_siniri(istemci, yonetici):
    p = await paket_ekle()
    # 31 Mart 21:30 UTC = 1 Nisan 00:30 İstanbul -> Nisan'a yazılır
    await paket_satiri(p, "0", OgrenciPaketiDurum.odendi, datetime(2026, 3, 31, 21, 30, tzinfo=timezone.utc), ozel=True, liste="100")
    # 28 Şubat 21:30 UTC = 1 Mart 00:30 İstanbul -> Mart'a yazılır
    await paket_satiri(p, "0", OgrenciPaketiDurum.odendi, datetime(2026, 2, 28, 21, 30, tzinfo=timezone.utc), ozel=True, liste="100")
    assert (await rapor(istemci, yonetici, 2026, 3)).json()["ozet"]["ucretsiz_paket_adedi"] == 1
    assert (await rapor(istemci, yonetici, 2026, 4)).json()["ozet"]["ucretsiz_paket_adedi"] == 1
    assert (await rapor(istemci, yonetici, 2026, 2)).json()["ozet"]["ucretsiz_paket_adedi"] == 0


async def test_bekleyen_ve_gecikmis(istemci, yonetici):
    p = await paket_ekle()
    simdi = datetime.now(timezone.utc)
    await paket_satiri(p, "1000", OgrenciPaketiDurum.odeme_bekliyor)  # yeni
    await paket_satiri(p, "2000", OgrenciPaketiDurum.odeme_bekliyor, simdi - timedelta(days=3))
    await paket_satiri(p, "4000", OgrenciPaketiDurum.odeme_bekliyor, simdi - timedelta(days=9))
    await paket_satiri(p, "8000", OgrenciPaketiDurum.odeme_bekliyor, simdi - timedelta(days=9), sentetik=True)
    await paket_satiri(p, "16000", OgrenciPaketiDurum.iptal, simdi - timedelta(days=30))
    await paket_satiri(p, "32000", OgrenciPaketiDurum.odendi, simdi - timedelta(days=30))
    for ay in ((2020, 1), (2026, 3)):  # dönemden bağımsız
        b = (await rapor(istemci, yonetici, *ay)).json()["bekleyen"]
        assert b == {"adet": 3, "tutar": "7000.00", "gecikmis_adet": 1, "gecikmis_tutar": "4000.00"}


async def test_gecikme_siniri_bekleyenler_ucuyla_tutarli(istemci, yonetici):
    p = await paket_ekle()
    await paket_satiri(p, "100", OgrenciPaketiDurum.odeme_bekliyor)
    sinir_gun = bugun() - timedelta(days=7)
    from app.api.raporlar import _gun_baslangici

    # Tam 7 gün önceki günün sonu: bekleme_gun = 7, gecikmiş değil; bir gün önce: 8, gecikmiş
    await paket_satiri(p, "200", OgrenciPaketiDurum.odeme_bekliyor, _gun_baslangici(sinir_gun) + timedelta(hours=23))
    await paket_satiri(p, "400", OgrenciPaketiDurum.odeme_bekliyor, _gun_baslangici(sinir_gun) - timedelta(hours=1))
    b = (await rapor(istemci, yonetici)).json()["bekleyen"]
    assert b["adet"] == 3 and b["gecikmis_adet"] == 1 and b["gecikmis_tutar"] == "400.00"
    liste = (await istemci.get("/api/odemeler/bekleyenler", headers=yonetici)).json()
    assert sum(1 for x in liste if x["bekleme_gun"] > 7) == 1


async def test_aylik_seri_ay_sinirlari(istemci, yonetici):
    p = await paket_ekle()
    await odeme_ekle(p, "100", date(2026, 1, 1))
    await odeme_ekle(p, "200", date(2026, 1, 31))
    await odeme_ekle(p, "400", date(2025, 12, 31))
    await odeme_ekle(p, "800", date(2025, 2, 1))  # seri başı (ilk günü)
    await odeme_ekle(p, "1600", date(2025, 1, 31))  # seri dışı
    await odeme_ekle(p, "3200", date(2026, 2, 1))  # seçilen aydan sonra
    await odeme_ekle(p, "50", date(2026, 1, 15), iptal=True)
    j = (await rapor(istemci, yonetici, 2026, 1)).json()
    seri = j["aylik_seri"]
    assert len(seri) == 12
    assert (seri[0]["yil"], seri[0]["ay"]) == (2025, 2) and (seri[-1]["yil"], seri[-1]["ay"]) == (2026, 1)
    ay_harita = {(x["yil"], x["ay"]): x for x in seri}
    assert ay_harita[(2026, 1)]["tutar"] == "300.00" and ay_harita[(2026, 1)]["adet"] == 2
    assert ay_harita[(2025, 12)]["tutar"] == "400.00"
    assert ay_harita[(2025, 11)]["tutar"] == "0.00" and ay_harita[(2025, 11)]["adet"] == 0
    assert ay_harita[(2025, 2)]["tutar"] == "800.00" and (2025, 1) not in ay_harita
    assert [(x["yil"], x["ay"]) for x in seri] == [(2025, m) for m in range(2, 13)] + [(2026, 1)]
    # Nisan 2025 serisi 2024'e uzanır
    seri3 = (await rapor(istemci, yonetici, 2025, 4)).json()["aylik_seri"]
    assert (seri3[0]["yil"], seri3[0]["ay"]) == (2024, 5) and (seri3[-1]["yil"], seri3[-1]["ay"]) == (2025, 4)
    assert [x for x in seri3 if (x["yil"], x["ay"]) == (2025, 2)][0]["tutar"] == "800.00"


async def test_artik_yil_gunleri(istemci, yonetici):
    j = (await rapor(istemci, yonetici, 2028, 2)).json()
    assert len(j["gunluk"]) == 29 and j["donem"]["bitis"] == "2028-02-29"


@pytest.mark.parametrize("sorgu", ["yil=abc", "ay=0", "ay=13", "ay=x", "yil=1999", "yil=2101"])
async def test_gecersiz_parametre(istemci, yonetici, sorgu):
    assert (await istemci.get(f"/api/raporlar/gelir?{sorgu}", headers=yonetici)).status_code == 422


async def test_csv_bicim_ve_audit(istemci, yonetici):
    p = await paket_ekle("Aylık 8 Ders")
    await odeme_ekle(p, "3400", date(2026, 3, 5), OdemeYontemi.havale_eft, aciklama="Mart; aidatı", ad="Zeynep", soyad="Kaya")
    await odeme_ekle(p, "1234.5", date(2026, 3, 6), aciklama="=HYPERLINK(\"x\")", ad="@Ali", soyad="Veli", iptal=True)
    await odeme_ekle(p, "10", date(2026, 3, 7), aciklama="-5", ad="Ayşe", soyad="Demir")
    await odeme_ekle(p, "10", date(2026, 3, 7), aciklama="\tgizli", ad="Can", soyad="Er")
    await odeme_ekle(p, "10", date(2026, 3, 7), aciklama="+90", ad="Can", soyad="Er")
    await odeme_ekle(p, "10", date(2026, 3, 7), aciklama="\rx", ad="Can", soyad="Er")
    await odeme_ekle(p, "99", date(2026, 3, 8), sentetik=True)
    await odeme_ekle(p, "77", date(2026, 4, 8))
    r = await istemci.get("/api/raporlar/gelir.csv?baslangic=2026-03-01&bitis=2026-03-31", headers=yonetici)
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="gelir-20260301-20260331.csv"'
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith(b"\xef\xbb\xbf")
    metin = r.content.decode("utf-8-sig")
    satirlar = metin.split("\r\n")
    assert satirlar[0] == "Tarih;Öğrenci;Paket;Tutar;Yöntem;Durum;Açıklama;İşlemi yapan"
    assert satirlar[1] == '2026-03-05;Zeynep Kaya;Aylık 8 Ders;3400,00;Havale/EFT;Geçerli;"Mart; aidatı";'
    assert satirlar[2].startswith("2026-03-06;'@Ali Veli;Aylık 8 Ders;1234,50;Nakit;İptal;")
    assert "\"'=HYPERLINK(\"\"x\"\")\"" in satirlar[2]
    assert ";'-5;" in satirlar[3]
    assert "'\tgizli" in metin and ";'+90;" in metin and "'\rx" in metin
    assert "99,00" not in metin and "77,00" not in metin
    async with SessionLocal() as s:
        log = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "rapor_disa_aktarildi"))).scalar_one()
    assert log.detay == {"baslangic": "2026-03-01", "bitis": "2026-03-31", "satir_sayisi": 6}
    assert "Zeynep" not in str(log.detay)


async def test_csv_bos_ve_varsayilan_aralik(istemci, yonetici):
    r = await istemci.get("/api/raporlar/gelir.csv", headers=yonetici)
    assert r.status_code == 200
    t = bugun()
    ilk = t.replace(day=1)
    assert f"gelir-{ilk:%Y%m%d}-" in r.headers["content-disposition"]
    assert r.content.decode("utf-8-sig") == "Tarih;Öğrenci;Paket;Tutar;Yöntem;Durum;Açıklama;İşlemi yapan\r\n"


@pytest.mark.parametrize(
    "sorgu",
    [
        "baslangic=2026-03-10&bitis=2026-03-09",
        "baslangic=2025-01-01&bitis=2026-01-02",  # 367 gün
        "baslangic=bozuk",
    ],
)
async def test_csv_gecersiz_aralik(istemci, yonetici, sorgu):
    assert (await istemci.get(f"/api/raporlar/gelir.csv?{sorgu}", headers=yonetici)).status_code == 422


async def test_csv_366_gun_kabul(istemci, yonetici):
    r = await istemci.get("/api/raporlar/gelir.csv?baslangic=2027-01-01&bitis=2027-12-31", headers=yonetici)
    assert r.status_code == 200
    r = await istemci.get("/api/raporlar/gelir.csv?baslangic=2028-01-01&bitis=2028-12-31", headers=yonetici)
    assert r.status_code == 200  # 366 gün (artık yıl)
