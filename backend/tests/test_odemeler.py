import asyncio
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app import ders_hakki
from app.db import SessionLocal
from app.models import DenetimKaydi, DersHakkiHareketi, HareketTuru, Odeme, Ogrenci, OgrenciPaketi, Rol
from app.oturumlar import bugun
from tests.test_paketler import ata, giris, ogrenci_olustur, paket_olustur


@pytest.fixture
async def yonetici(istemci):
    return await giris(istemci, "yonetici@kulup.com", Rol.admin)


async def bekleyen_paket(istemci, yonetici, ad="Deneme", soyad="Öğrenci", **ek):
    """Yeni öğrenci + paket + atama; (ogrenci_id, ogrenci_paketi_id) döner."""
    async with SessionLocal() as s:
        o = Ogrenci(ad=ad, soyad=soyad, dogum_tarihi=date(2015, 5, 10))
        s.add(o)
        await s.commit()
        oid = str(o.id)
    p = await paket_olustur(istemci, yonetici)
    r = await ata(istemci, yonetici, oid, p["id"], **ek)
    assert r.status_code == 201, r.text
    return oid, r.json()["id"]


async def bakiye(oid):
    import uuid

    async with SessionLocal() as s:
        return await ders_hakki.bakiye(s, uuid.UUID(oid))


def ode(istemci, yonetici, opid, **govde):
    return istemci.post(
        f"/api/ogrenci-paketleri/{opid}/odeme", json={"yontem": "nakit", **govde}, headers=yonetici
    )


async def test_yetki(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici)
    antrenor = await giris(istemci, "hoca@kulup.com", Rol.antrenor)
    uclar = [
        ("post", f"/api/ogrenci-paketleri/{opid}/odeme", {"yontem": "nakit"}),
        ("post", f"/api/odemeler/{opid}/iptal", {"neden": "deneme"}),
        ("get", "/api/odemeler", None),
        ("get", "/api/odemeler/bekleyenler", None),
    ]
    for yontem, yol, govde in uclar:
        kw = {"json": govde} if govde else {}
        assert (await getattr(istemci, yontem)(yol, headers=antrenor, **kw)).status_code == 403
        assert (await getattr(istemci, yontem)(yol, **kw)).status_code == 401


async def test_odeme_al_durum_ders_yukler(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici)
    r = await ode(istemci, yonetici, opid, yontem="pos", aciklama="Mayıs aidatı")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["durum"] == "odendi" and j["toplam_odenen"] == "3400.00"
    assert len(j["odemeler"]) == 1
    od = j["odemeler"][0]
    assert od["tutar"] == "3400.00" and od["yontem"] == "pos" and od["iptal"] is False
    assert od["tarih"] == bugun().isoformat() and od["aciklama"] == "Mayıs aidatı"
    assert od["alan_ad"] == "yonetici@kulup.com"
    assert (await bakiye(oid))["normal"] == 8
    async with SessionLocal() as s:
        h = (await s.execute(select(DersHakkiHareketi))).scalar_one()
        assert h.tur == HareketTuru.paket_yuklemesi and h.miktar == 8 and str(h.ogrenci_paketi_id) == opid
        assert h.odeme_id is not None
        log = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "odeme_alindi"))).scalar_one()
        assert log.detay["tutar"] == "3400.00" and log.detay["yontem"] == "pos"
    # GET listesinde de odemeler döner
    liste = (await istemci.get(f"/api/ogrenciler/{oid}/paketler", headers=yonetici)).json()
    assert len(liste[0]["odemeler"]) == 1


async def test_ozel_fiyat_tutar_olarak_alinir(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici, ozel_fiyat="2500.50", ozel_fiyat_nedeni="Kardeş indirimi")
    j = (await ode(istemci, yonetici, opid)).json()
    assert j["odemeler"][0]["tutar"] == "2500.50" and j["toplam_odenen"] == "2500.50"


async def test_ikinci_odeme_ve_iptal_edilmis_pakete_409(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici)
    assert (await ode(istemci, yonetici, opid)).status_code == 200
    assert (await ode(istemci, yonetici, opid)).status_code == 409
    assert (await bakiye(oid))["normal"] == 8
    oid2, opid2 = await bekleyen_paket(istemci, yonetici, ad="Baska")
    assert (await istemci.post(f"/api/ogrenci-paketleri/{opid2}/iptal", headers=yonetici)).status_code == 200
    assert (await ode(istemci, yonetici, opid2)).status_code == 409
    assert (await ode(istemci, yonetici, "00000000-0000-0000-0000-000000000000")).status_code == 404


async def test_tarih_kurallari(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici)
    yarin = (bugun() + timedelta(days=1)).isoformat()
    assert (await ode(istemci, yonetici, opid, tarih=yarin)).status_code == 422
    assert (await ode(istemci, yonetici, opid, yontem="kripto")).status_code == 422
    assert (await ode(istemci, yonetici, opid, tutar="1")).status_code == 422  # tutar gönderilemez
    assert (await ode(istemci, yonetici, opid, aciklama="x" * 301)).status_code == 422
    gecmis = (bugun() - timedelta(days=3)).isoformat()
    r = await ode(istemci, yonetici, opid, tarih=gecmis)
    assert r.status_code == 200 and r.json()["odemeler"][0]["tarih"] == gecmis


async def test_ucretsiz_paket_odeme_satiri_yazmaz_ders_yukler(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici, ozel_fiyat="0", ozel_fiyat_nedeni="Burslu öğrenci")
    j = (await ode(istemci, yonetici, opid)).json()
    assert j["durum"] == "odendi" and j["odemeler"] == [] and j["toplam_odenen"] == "0.00"
    assert (await bakiye(oid))["normal"] == 8
    async with SessionLocal() as s:
        assert (await s.execute(select(func.count()).select_from(Odeme))).scalar_one() == 0
        log = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "odeme_alindi"))).scalar_one()
        assert log.detay["ucretsiz_paket"] is True
    assert (await ode(istemci, yonetici, opid)).status_code == 409


async def test_pasif_ogrenci_icin_odeme_alinir(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici)
    async with SessionLocal() as s:
        import uuid

        o = await s.get(Ogrenci, uuid.UUID(oid))
        from app.models import OgrenciDurum

        o.durum = OgrenciDurum.pasif
        await s.commit()
    assert (await ode(istemci, yonetici, opid)).status_code == 200


async def test_odeme_iptali_ters_kayit_ve_yeniden_odeme(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici)
    j = (await ode(istemci, yonetici, opid)).json()
    odeme_id = j["odemeler"][0]["id"]
    assert (await istemci.post(f"/api/odemeler/{odeme_id}/iptal", json={"neden": "x"}, headers=yonetici)).status_code == 422
    r = await istemci.post(f"/api/odemeler/{odeme_id}/iptal", json={"neden": "Yanlış tutar"}, headers=yonetici)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["durum"] == "odeme_bekliyor" and j["toplam_odenen"] == "0.00"
    assert j["odemeler"][0]["iptal"] is True and j["odemeler"][0]["iptal_nedeni"] == "Yanlış tutar"
    assert (await bakiye(oid))["normal"] == 0
    async with SessionLocal() as s:
        h = (await s.execute(select(DersHakkiHareketi).order_by(DersHakkiHareketi.id))).scalars().all()
        assert [x.tur for x in h] == [HareketTuru.paket_yuklemesi, HareketTuru.iptal]
        assert h[1].iptal_edilen_id == h[0].id and h[1].miktar == -8 and h[1].sayac == h[0].sayac
        assert (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "odeme_iptal_edildi"))).scalar_one()
    # çift iptal
    assert (await istemci.post(f"/api/odemeler/{odeme_id}/iptal", json={"neden": "tekrar"}, headers=yonetici)).status_code == 409
    assert (await istemci.post("/api/odemeler/00000000-0000-0000-0000-000000000000/iptal", json={"neden": "tekrar"}, headers=yonetici)).status_code == 404
    # tekrar ödeme alınabilir, ders yeniden yüklenir
    j = (await ode(istemci, yonetici, opid, yontem="havale_eft")).json()
    assert j["durum"] == "odendi" and j["toplam_odenen"] == "3400.00" and len(j["odemeler"]) == 2
    assert (await bakiye(oid))["normal"] == 8
    # yeni ödemeyi de iptal edebiliriz
    yeni = next(o["id"] for o in j["odemeler"] if not o["iptal"])
    assert (await istemci.post(f"/api/odemeler/{yeni}/iptal", json={"neden": "tekrar iptal"}, headers=yonetici)).status_code == 200
    assert (await bakiye(oid))["normal"] == 0


async def test_iptal_bakiyeyi_negatife_dusurebilir(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici)
    odeme_id = (await ode(istemci, yonetici, opid)).json()["odemeler"][0]["id"]
    import uuid

    async with SessionLocal() as s:
        s.add(DersHakkiHareketi(ogrenci_id=uuid.UUID(oid), sayac="normal", miktar=-10, tur=HareketTuru.ders_kullanimi))
        await s.commit()
    assert (await istemci.post(f"/api/odemeler/{odeme_id}/iptal", json={"neden": "iade"}, headers=yonetici)).status_code == 200
    assert (await bakiye(oid))["normal"] == -10


async def test_iptal_edilen_odeme_paket_iptaline_engel_degildir(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici)
    odeme_id = (await ode(istemci, yonetici, opid)).json()["odemeler"][0]["id"]
    await istemci.post(f"/api/odemeler/{odeme_id}/iptal", json={"neden": "iade"}, headers=yonetici)
    assert (await istemci.post(f"/api/ogrenci-paketleri/{opid}/iptal", headers=yonetici)).status_code == 200


async def test_eszamanli_iki_odeme_biri_409(istemci, yonetici):
    oid, opid = await bekleyen_paket(istemci, yonetici)
    yanitlar = await asyncio.gather(ode(istemci, yonetici, opid), ode(istemci, yonetici, opid, yontem="pos"))
    assert sorted(y.status_code for y in yanitlar) == [200, 409]
    assert (await bakiye(oid))["normal"] == 8
    async with SessionLocal() as s:
        assert (await s.execute(select(func.count()).select_from(Odeme))).scalar_one() == 1


async def test_odeme_listesi_suzgec_ozet_sayfalama_arama(istemci, yonetici):
    o1, p1 = await bekleyen_paket(istemci, yonetici, ad="Ayşe", soyad="Yılmaz")
    o2, p2 = await bekleyen_paket(istemci, yonetici, ad="Mehmet", soyad="Kaya", ozel_fiyat="1000", ozel_fiyat_nedeni="İndirim")
    o3, p3 = await bekleyen_paket(istemci, yonetici, ad="Zeynep", soyad="Demir")
    await ode(istemci, yonetici, p1, yontem="nakit")
    await ode(istemci, yonetici, p2, yontem="pos")
    j3 = (await ode(istemci, yonetici, p3, yontem="nakit", tarih=bugun().isoformat())).json()
    await istemci.post(f"/api/odemeler/{j3['odemeler'][0]['id']}/iptal", json={"neden": "hata"}, headers=yonetici)
    # sentetik öğrenci ödemesi görünmez
    async with SessionLocal() as s:
        import uuid

        s.add(Ogrenci(ad="Gizli", soyad="Sentetik", dogum_tarihi=date(2015, 1, 1), sentetik=True))
        await s.commit()

    j = (await istemci.get("/api/odemeler?baslangic=2000-01-01&bitis=2999-01-01", headers=yonetici)).json()
    assert j["toplam"] == 3 and len(j["kayitlar"]) == 3
    assert j["ozet"]["toplam_tutar"] == "4400.00" and j["ozet"]["adet"] == 2  # iptal hariç
    dagilim = {d["yontem"]: d for d in j["ozet"]["yontem_dagilimi"]}
    assert dagilim["nakit"] == {"yontem": "nakit", "tutar": "3400.00", "adet": 1}
    assert dagilim["pos"]["tutar"] == "1000.00"
    satir = next(k for k in j["kayitlar"] if k["iptal"])
    assert satir["ogrenci"]["ad"] == "Zeynep" and satir["iptal_nedeni"] == "hata" and satir["paket_adi"] == "Aylık 8 Ders"
    assert satir["alan_ad"] == "yonetici@kulup.com"

    # varsayılan: bu ay
    assert (await istemci.get("/api/odemeler", headers=yonetici)).json()["toplam"] == 3
    # geçmiş dönem boş
    bos = (await istemci.get("/api/odemeler?baslangic=2000-01-01&bitis=2000-01-31", headers=yonetici)).json()
    assert bos["toplam"] == 0 and bos["ozet"] == {"toplam_tutar": "0.00", "adet": 0, "yontem_dagilimi": []}
    assert (await istemci.get("/api/odemeler?baslangic=2001-01-01&bitis=2000-01-01", headers=yonetici)).status_code == 422
    # yöntem, iptal hariç, arama
    j = (await istemci.get("/api/odemeler?yontem=nakit", headers=yonetici)).json()
    assert j["toplam"] == 2 and j["ozet"]["adet"] == 1
    j = (await istemci.get("/api/odemeler?iptal_dahil=false", headers=yonetici)).json()
    assert j["toplam"] == 2 and not any(k["iptal"] for k in j["kayitlar"])
    j = (await istemci.get("/api/odemeler?q=mehmet kaya", headers=yonetici)).json()
    assert j["toplam"] == 1 and j["ozet"]["toplam_tutar"] == "1000.00"
    assert (await istemci.get("/api/odemeler?q=Gizli", headers=yonetici)).json()["toplam"] == 0
    assert (await istemci.get("/api/odemeler?q=%25", headers=yonetici)).json()["toplam"] == 0
    # sayfalama: özet sayfadan bağımsız
    j = (await istemci.get("/api/odemeler?boyut=2&sayfa=2", headers=yonetici)).json()
    assert len(j["kayitlar"]) == 1 and j["toplam"] == 3 and j["ozet"]["adet"] == 2
    assert (await istemci.get("/api/odemeler?boyut=201", headers=yonetici)).status_code == 422


async def test_en_yeni_once_sirasi(istemci, yonetici):
    _, p1 = await bekleyen_paket(istemci, yonetici, ad="Eski")
    _, p2 = await bekleyen_paket(istemci, yonetici, ad="Yeni")
    await ode(istemci, yonetici, p1, tarih=(bugun() - timedelta(days=1)).isoformat())
    await ode(istemci, yonetici, p2, tarih=bugun().isoformat())
    j = (await istemci.get("/api/odemeler?baslangic=2000-01-01&bitis=2999-01-01", headers=yonetici)).json()
    assert [k["ogrenci"]["ad"] for k in j["kayitlar"]] == ["Yeni", "Eski"]


async def test_bekleyenler(istemci, yonetici):
    o1, p1 = await bekleyen_paket(istemci, yonetici, ad="Birinci")
    o2, p2 = await bekleyen_paket(istemci, yonetici, ad="Ikinci")
    o3, p3 = await bekleyen_paket(istemci, yonetici, ad="Ucuncu")
    await ode(istemci, yonetici, p3)
    async with SessionLocal() as s:
        import uuid
        from datetime import datetime, timezone

        op = await s.get(OgrenciPaketi, uuid.UUID(p2))
        op.olusturma = datetime.now(timezone.utc) - timedelta(days=5)
        await s.commit()
    j = (await istemci.get("/api/odemeler/bekleyenler", headers=yonetici)).json()
    assert [k["ogrenci"]["ad"] for k in j] == ["Ikinci", "Birinci"]  # eski önce
    assert j[0]["ogrenci_paketi_id"] == p2 and j[0]["bekleme_gun"] in (5, 4, 6) and j[1]["bekleme_gun"] == 0
    assert j[0]["uygulanan_fiyat"] == "3400.00" and j[0]["paket_adi"] == "Aylık 8 Ders"
    assert j[0]["atama_tarihi"]
    # ödeme iptal edilince yeniden bekleyenlere düşer
    od = (await istemci.get(f"/api/ogrenciler/{o3}/paketler", headers=yonetici)).json()[0]["odemeler"][0]["id"]
    await istemci.post(f"/api/odemeler/{od}/iptal", json={"neden": "hata"}, headers=yonetici)
    assert len((await istemci.get("/api/odemeler/bekleyenler", headers=yonetici)).json()) == 3
