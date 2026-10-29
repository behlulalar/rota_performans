from datetime import date

import pytest
from sqlalchemy import select

from app.api.paketler import ay_ekle
from app.db import SessionLocal
from app.models import DenetimKaydi, Odeme, OdemeYontemi, Ogrenci, OgrenciDurum, OgrenciPaketi, Rol
from tests.conftest import SIFRE, kullanici_olustur


async def giris(istemci, eposta, rol):
    await kullanici_olustur(eposta, rol)
    yanit = await istemci.post("/api/auth/login", json={"giris": eposta, "sifre": SIFRE})
    return {"Authorization": f"Bearer {yanit.json()['access_token']}"}


@pytest.fixture
async def yonetici(istemci):
    return await giris(istemci, "yonetici@kulup.com", Rol.admin)


async def ogrenci_olustur(durum=OgrenciDurum.aktif):
    async with SessionLocal() as s:
        o = Ogrenci(ad="Deneme", soyad="Öğrenci", dogum_tarihi=date(2015, 5, 10), durum=durum)
        s.add(o)
        await s.commit()
        return str(o.id)


async def paket_olustur(istemci, baslik, **ek):
    govde = {"ad": "Aylık 8 Ders", "tur": "aylik", "ders_sayisi": 8, "sure_ay": 1, "varsayilan_fiyat": "3400.00"}
    govde.update(ek)
    yanit = await istemci.post("/api/paketler", json=govde, headers=baslik)
    assert yanit.status_code == 201, yanit.text
    return yanit.json()


async def ata(istemci, baslik, ogrenci_id, paket_id, **ek):
    return await istemci.post(
        f"/api/ogrenciler/{ogrenci_id}/paketler", json={"paket_id": paket_id, **ek}, headers=baslik
    )


async def test_yetki(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    o = await ogrenci_olustur()
    antrenor = await giris(istemci, "hoca@kulup.com", Rol.antrenor)
    uclar = [
        ("get", "/api/paketler", None),
        ("post", "/api/paketler", {"ad": "x", "tur": "aylik", "ders_sayisi": 1, "sure_ay": 1, "varsayilan_fiyat": "1"}),
        ("patch", f"/api/paketler/{p['id']}", {"aktif": False}),
        ("get", f"/api/ogrenciler/{o}/paketler", None),
        ("post", f"/api/ogrenciler/{o}/paketler", {"paket_id": p["id"]}),
        ("post", f"/api/ogrenci-paketleri/{p['id']}/iptal", None),
    ]
    for yontem, yol, govde in uclar:
        assert (await getattr(istemci, yontem)(yol, headers=antrenor, **({"json": govde} if govde else {}))).status_code == 403
        assert (await getattr(istemci, yontem)(yol, **({"json": govde} if govde else {}))).status_code == 401


async def test_paket_crud(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    assert p["varsayilan_fiyat"] == "3400.00" and p["aktif"] is True and p["aciklama"] is None
    for alan, deger in (("ders_sayisi", 0), ("sure_ay", 0), ("tur", "haftalik"), ("ders_sayisi", None), ("tur", None)):
        r = await istemci.patch(f"/api/paketler/{p['id']}", json={alan: deger}, headers=yonetici)
        assert r.status_code == 422, (alan, deger)
    r = await istemci.patch(
        f"/api/paketler/{p['id']}", json={"ad": "Yeni ad", "varsayilan_fiyat": "3500.5"}, headers=yonetici
    )
    assert r.status_code == 200
    assert r.json()["ad"] == "Yeni Ad" and r.json()["varsayilan_fiyat"] == "3500.50"
    assert r.json()["ders_sayisi"] == 8
    assert (await istemci.patch(f"/api/paketler/{p['id']}", json={"ad": None}, headers=yonetici)).status_code == 422
    assert (await istemci.delete(f"/api/paketler/{p['id']}", headers=yonetici)).status_code == 405
    await istemci.patch(f"/api/paketler/{p['id']}", json={"aktif": False}, headers=yonetici)
    assert len((await istemci.get("/api/paketler", headers=yonetici)).json()) == 1
    assert (await istemci.get("/api/paketler?aktif=true", headers=yonetici)).json() == []
    assert len((await istemci.get("/api/paketler?aktif=false", headers=yonetici)).json()) == 1
    assert (await istemci.patch("/api/paketler/00000000-0000-0000-0000-000000000000", json={"aktif": True}, headers=yonetici)).status_code == 404
    async with SessionLocal() as s:
        islemler = {k.islem for k in (await s.execute(select(DenetimKaydi))).scalars()}
    assert {"paket_olusturuldu", "paket_guncellendi"} <= islemler


@pytest.mark.parametrize(
    "ek",
    [{"ders_sayisi": 0}, {"sure_ay": 0}, {"varsayilan_fiyat": "-1"}, {"varsayilan_fiyat": "10.123"}, {"tur": "haftalik"}, {"ad": ""}],
)
async def test_paket_gecersiz_girdi(istemci, yonetici, ek):
    govde = {"ad": "A", "tur": "aylik", "ders_sayisi": 8, "sure_ay": 1, "varsayilan_fiyat": "100"}
    govde.update(ek)
    assert (await istemci.post("/api/paketler", json=govde, headers=yonetici)).status_code == 422


async def test_atama_kopyalama_ve_liste(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    o = await ogrenci_olustur()
    r = await ata(istemci, yonetici, o, p["id"], baslangic="2026-01-15")
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["ders_sayisi"] == 8 and a["liste_fiyati"] == "3400.00" and a["uygulanan_fiyat"] == "3400.00"
    assert a["fiyat_ozel_mi"] is False and a["durum"] == "odeme_bekliyor"
    assert a["baslangic"] == "2026-01-15" and a["bitis"] == "2026-02-15"
    assert a["toplam_odenen"] == "0.00" and a["paket_adi"] == "Aylık 8 Ders"
    # Paket sonradan değişse de kopya bozulmaz.
    await istemci.patch(f"/api/paketler/{p['id']}", json={"varsayilan_fiyat": "5000"}, headers=yonetici)
    liste = (await istemci.get(f"/api/ogrenciler/{o}/paketler", headers=yonetici)).json()
    assert len(liste) == 1 and liste[0]["liste_fiyati"] == "3400.00"
    async with SessionLocal() as s:
        op = (await s.execute(select(OgrenciPaketi))).scalar_one()
        assert op.fiyat_degistiren_id is None and op.olusturan_id is not None


async def test_paket_tum_alanlar_ve_aciklama_duzenlenir_atanmis_kopya_bozulmaz(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici, aciklama="  Haftada 2 ders  ")
    assert p["aciklama"] == "Haftada 2 ders"
    o = await ogrenci_olustur()
    a = (await ata(istemci, yonetici, o, p["id"], baslangic="2026-01-15")).json()

    r = await istemci.patch(
        f"/api/paketler/{p['id']}",
        json={"tur": "uc_aylik", "ders_sayisi": 24, "sure_ay": 3, "varsayilan_fiyat": "9000", "aciklama": "Yeni açıklama"},
        headers=yonetici,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["tur"], d["ders_sayisi"], d["sure_ay"], d["varsayilan_fiyat"], d["aciklama"]) == (
        "uc_aylik", 24, 3, "9000.00", "Yeni açıklama",
    )
    # Daha önce atanan paket eski haliyle kalır.
    liste = (await istemci.get(f"/api/ogrenciler/{o}/paketler", headers=yonetici)).json()
    assert liste[0]["id"] == a["id"] and liste[0]["ders_sayisi"] == 8 and liste[0]["liste_fiyati"] == "3400.00"
    assert liste[0]["bitis"] == "2026-02-15"
    # Yeni atama yeni değerleri alır.
    o2 = await ogrenci_olustur()
    b = (await ata(istemci, yonetici, o2, p["id"], baslangic="2026-01-15")).json()
    assert b["ders_sayisi"] == 24 and b["liste_fiyati"] == "9000.00" and b["bitis"] == "2026-04-15"
    # Açıklama boş gönderilince silinir; hiç gönderilmezse korunur.
    r = await istemci.patch(f"/api/paketler/{p['id']}", json={"ad": "Başka"}, headers=yonetici)
    assert r.json()["aciklama"] == "Yeni açıklama"
    r = await istemci.patch(f"/api/paketler/{p['id']}", json={"aciklama": "  "}, headers=yonetici)
    assert r.json()["aciklama"] is None
    assert (await istemci.patch(f"/api/paketler/{p['id']}", json={"aciklama": "x" * 1001}, headers=yonetici)).status_code == 422


async def test_baslangic_varsayilan_bugun(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    o = await ogrenci_olustur()
    a = (await ata(istemci, yonetici, o, p["id"])).json()
    assert a["baslangic"] == date.today().isoformat()


async def test_ozel_fiyat(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    o = await ogrenci_olustur()
    # Neden zorunlu
    assert (await ata(istemci, yonetici, o, p["id"], ozel_fiyat="3000")).status_code == 422
    assert (await ata(istemci, yonetici, o, p["id"], ozel_fiyat="3000", ozel_fiyat_nedeni="ab")).status_code == 422
    assert (await ata(istemci, yonetici, o, p["id"], ozel_fiyat="3000", ozel_fiyat_nedeni="x" * 201)).status_code == 422
    assert (await ata(istemci, yonetici, o, p["id"], ozel_fiyat="-1", ozel_fiyat_nedeni="indirim")).status_code == 422
    assert (await ata(istemci, yonetici, o, p["id"], ozel_nedeni_yok="1")).status_code == 422
    assert (await ata(istemci, yonetici, o, p["id"], ozel_fiyat_nedeni="nedensiz")).status_code == 422
    r = await ata(istemci, yonetici, o, p["id"], ozel_fiyat=3000, ozel_fiyat_nedeni="Kardeş indirimi")
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["uygulanan_fiyat"] == "3000.00" and a["liste_fiyati"] == "3400.00" and a["fiyat_ozel_mi"] is True
    async with SessionLocal() as s:
        op = (await s.execute(select(OgrenciPaketi))).scalar_one()
        assert op.fiyat_degistiren_id is not None
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ogrenci_paketi_atandi"))).scalar_one()
        assert k.detay["ozel_fiyat_nedeni"] == "Kardeş indirimi"


async def test_ozel_fiyat_liste_ile_ayni_ozel_degil(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    o = await ogrenci_olustur()
    a = (await ata(istemci, yonetici, o, p["id"], ozel_fiyat="3400", ozel_fiyat_nedeni="aynı fiyat")).json()
    assert a["fiyat_ozel_mi"] is False
    # Ücretsiz (0) geçerli
    await istemci.post(f"/api/ogrenci-paketleri/{a['id']}/iptal", headers=yonetici)
    b = (await ata(istemci, yonetici, o, p["id"], ozel_fiyat="0", ozel_fiyat_nedeni="burslu")).json()
    assert b["uygulanan_fiyat"] == "0.00" and b["fiyat_ozel_mi"] is True


def test_ay_ekle():
    assert ay_ekle(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert ay_ekle(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert ay_ekle(date(2026, 11, 30), 3) == date(2027, 2, 28)
    assert ay_ekle(date(2026, 12, 15), 1) == date(2027, 1, 15)
    assert ay_ekle(date(2026, 3, 31), 12) == date(2027, 3, 31)
    assert ay_ekle(date(2026, 8, 31), 6) == date(2027, 2, 28)


async def test_bitis_ay_sonu(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    o = await ogrenci_olustur()
    a = (await ata(istemci, yonetici, o, p["id"], baslangic="2028-01-31")).json()
    assert a["bitis"] == "2028-02-29"
    y = await paket_olustur(istemci, yonetici, ad="Yıllık", tur="yillik", sure_ay=12, ders_sayisi=96)
    o2 = await ogrenci_olustur()
    assert (await ata(istemci, yonetici, o2, y["id"], baslangic="2028-02-29")).json()["bitis"] == "2029-02-28"


async def test_pasif_paket_atanamaz(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    await istemci.patch(f"/api/paketler/{p['id']}", json={"aktif": False}, headers=yonetici)
    o = await ogrenci_olustur()
    assert (await ata(istemci, yonetici, o, p["id"])).status_code == 409
    assert (await ata(istemci, yonetici, o, "00000000-0000-0000-0000-000000000000")).status_code == 404


async def test_ikinci_bekleyen_paket_409(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    o = await ogrenci_olustur()
    assert (await ata(istemci, yonetici, o, p["id"])).status_code == 201
    r = await ata(istemci, yonetici, o, p["id"])
    assert r.status_code == 409 and r.json()["detail"] == "Bu öğrencinin ödeme bekleyen bir paketi var"
    # Başka öğrenci etkilenmez
    o2 = await ogrenci_olustur()
    assert (await ata(istemci, yonetici, o2, p["id"])).status_code == 201


async def test_pasif_ve_olmayan_ogrenci(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    o = await ogrenci_olustur(OgrenciDurum.pasif)
    assert (await ata(istemci, yonetici, o, p["id"])).status_code == 409
    assert (await ata(istemci, yonetici, "00000000-0000-0000-0000-000000000000", p["id"])).status_code == 404
    assert (await istemci.get("/api/ogrenciler/00000000-0000-0000-0000-000000000000/paketler", headers=yonetici)).status_code == 404


async def test_iptal_kurallari(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici)
    o = await ogrenci_olustur()
    a = (await ata(istemci, yonetici, o, p["id"])).json()
    r = await istemci.post(f"/api/ogrenci-paketleri/{a['id']}/iptal", headers=yonetici)
    assert r.status_code == 200 and r.json()["durum"] == "iptal"
    # Tekrar iptal 409
    assert (await istemci.post(f"/api/ogrenci-paketleri/{a['id']}/iptal", headers=yonetici)).status_code == 409
    # İptalden sonra yeniden atanabilir
    b = (await ata(istemci, yonetici, o, p["id"])).json()
    # Ödemesi olan paket iptal edilemez
    async with SessionLocal() as s:
        s.add(Odeme(ogrenci_paketi_id=b["id"], tutar=100, yontem=OdemeYontemi.nakit))
        await s.commit()
    r = await istemci.post(f"/api/ogrenci-paketleri/{b['id']}/iptal", headers=yonetici)
    assert r.status_code == 409
    liste = (await istemci.get(f"/api/ogrenciler/{o}/paketler", headers=yonetici)).json()
    assert [x["id"] for x in liste] == [b["id"], a["id"]]  # yeniden eskiye
    assert liste[0]["toplam_odenen"] == "100.00" and liste[0]["durum"] == "odeme_bekliyor"
    assert (await istemci.post("/api/ogrenci-paketleri/00000000-0000-0000-0000-000000000000/iptal", headers=yonetici)).status_code == 404
    async with SessionLocal() as s:
        islemler = {k.islem for k in (await s.execute(select(DenetimKaydi))).scalars()}
    assert {"ogrenci_paketi_atandi", "ogrenci_paketi_iptal_edildi"} <= islemler
