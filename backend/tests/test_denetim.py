from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import DenetimKaydi, Rol
from tests.test_paketler import giris


@pytest.fixture
async def yonetici(istemci):
    return await giris(istemci, "yonetici@kulup.com", Rol.admin)


async def ekle(islem, zaman=None, **kw):
    async with SessionLocal() as s:
        k = DenetimKaydi(islem=islem, **kw)
        if zaman:
            k.zaman = zaman
        s.add(k)
        await s.commit()


async def sayi():
    async with SessionLocal() as s:
        return (await s.execute(select(func.count()).select_from(DenetimKaydi))).scalar_one()


async def test_yetki(istemci, yonetici):
    antrenor = await giris(istemci, "hoca@kulup.com", Rol.antrenor)
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    for yol in ("/api/denetim", "/api/denetim/islemler"):
        assert (await istemci.get(yol, headers=yonetici)).status_code == 200
        assert (await istemci.get(yol, headers=antrenor)).status_code == 403
        assert (await istemci.get(yol, headers=veli)).status_code == 403
        assert (await istemci.get(yol)).status_code == 401


async def test_giris_kaydi_ve_kullanici(istemci, yonetici):
    r = (await istemci.get("/api/denetim", headers=yonetici)).json()
    assert r["toplam"] >= 1
    s = next(x for x in r["items"] if x["islem"] == "giris_basarili")
    assert s["kullanici"]["giris"] == "yonetici@kulup.com"
    assert s["kullanici"]["rol"] == "admin"
    assert "sifre_ozeti" not in str(s)


async def test_filtreler(istemci, yonetici):
    await ekle("ogrenci_olusturuldu", hedef_tur="ogrenci", hedef_id="abc-123")
    await ekle("odeme_alindi", hedef_tur="odeme", hedef_id="xyz-999")
    r = (await istemci.get("/api/denetim?islem=odeme_alindi", headers=yonetici)).json()
    assert r["toplam"] == 1 and r["items"][0]["hedef_id"] == "xyz-999"
    r = (await istemci.get("/api/denetim?ara=abc-1", headers=yonetici)).json()
    assert [x["islem"] for x in r["items"]] == ["ogrenci_olusturuldu"]
    r = (await istemci.get("/api/denetim?ara=yonetici@kulup", headers=yonetici)).json()
    assert r["toplam"] >= 1 and all(x["kullanici"] for x in r["items"])
    kid = r["items"][0]["kullanici"]["id"]
    r = (await istemci.get(f"/api/denetim?kullanici_id={kid}", headers=yonetici)).json()
    assert r["toplam"] >= 1 and all(x["kullanici"]["id"] == kid for x in r["items"])
    assert (await istemci.get("/api/denetim?ara=%25", headers=yonetici)).json()["toplam"] == 0


async def test_tarih_araligi(istemci, yonetici):
    eski = datetime(2020, 3, 10, 12, 0, tzinfo=timezone.utc)
    await ekle("eski_islem", zaman=eski)
    r = (await istemci.get("/api/denetim?baslangic=2020-03-10&bitis=2020-03-10", headers=yonetici)).json()
    assert [x["islem"] for x in r["items"]] == ["eski_islem"]
    assert (await istemci.get("/api/denetim?baslangic=2020-03-11&bitis=2020-03-12", headers=yonetici)).json()["toplam"] == 0
    # Gece yarısından hemen önce (İstanbul): UTC 20:59 aynı gündür.
    await ekle("gece", zaman=datetime(2020, 5, 1, 20, 59, tzinfo=timezone.utc))
    r = (await istemci.get("/api/denetim?baslangic=2020-05-01&bitis=2020-05-01&islem=gece", headers=yonetici)).json()
    assert r["toplam"] == 1
    r = (await istemci.get("/api/denetim?baslangic=2020-05-02&bitis=2020-05-02&islem=gece", headers=yonetici)).json()
    assert r["toplam"] == 0


async def test_sayfalama_ve_sira(istemci, yonetici):
    t0 = datetime(2021, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        await ekle("sayfa_testi", zaman=t0 + timedelta(minutes=i), hedef_id=str(i))
    r = (await istemci.get("/api/denetim?islem=sayfa_testi&boyut=2&sayfa=1", headers=yonetici)).json()
    assert r["toplam"] == 5 and [x["hedef_id"] for x in r["items"]] == ["4", "3"]
    r = (await istemci.get("/api/denetim?islem=sayfa_testi&boyut=2&sayfa=3", headers=yonetici)).json()
    assert [x["hedef_id"] for x in r["items"]] == ["0"]
    assert (await istemci.get("/api/denetim?boyut=101", headers=yonetici)).status_code == 422
    assert (await istemci.get("/api/denetim?sayfa=0", headers=yonetici)).status_code == 422


async def test_hassas_anahtarlar_temizlenir(istemci, yonetici):
    await ekle("hassas", detay={"alan": "a", "yeni_sifre": "x", "Access_Token": "y", "ic": {"sifre": "z", "iyi": 1}})
    r = (await istemci.get("/api/denetim?islem=hassas", headers=yonetici)).json()
    assert r["items"][0]["detay"] == {"alan": "a", "ic": {"iyi": 1}}


async def test_islemler_listesi(istemci, yonetici):
    await ekle("zzz_islem")
    r = (await istemci.get("/api/denetim/islemler", headers=yonetici)).json()
    assert "giris_basarili" in r and "zzz_islem" in r
    assert len(r) == len(set(r)) and r == sorted(r)


async def test_goruntuleme_denetim_uretmez(istemci, yonetici):
    onceki = await sayi()
    await istemci.get("/api/denetim", headers=yonetici)
    await istemci.get("/api/denetim/islemler", headers=yonetici)
    assert await sayi() == onceki
