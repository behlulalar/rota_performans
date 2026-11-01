"""Kulüp ayarları: varsayılanlar, güncelleme/doğrulama, yetki, denetim ve bildirim davranışına etkisi."""
from datetime import timedelta

from sqlalchemy import select

from app import bildirim as bsvc
from app.db import SessionLocal
from app.models import DenetimKaydi, KulupAyari, Rol, YoklamaDurum
from tests.test_bildirim import T0, bildirimler, isaretle, ortam, oturum, yukle
from tests.test_yoklama import giris, yonetici  # noqa: F401  (fixture)

URL = "/api/ayarlar"


async def test_satir_yokken_varsayilanlar(istemci, yonetici):
    r = await istemci.get(URL, headers=yonetici)
    assert r.status_code == 200
    assert r.json() == {
        "ad": "Rota Performans Akademi", "telefon": None, "eposta": None, "adres": None,
        "geri_alma_dakika": 3, "azaldi_esigi": 2,
    }


async def test_kismi_ve_tam_guncelleme(istemci, yonetici):
    r = await istemci.put(URL, headers=yonetici, json={"telefon": "0532 123 45 67", "geri_alma_dakika": 7})
    assert r.status_code == 200
    j = r.json()
    assert j["telefon"] == "+905321234567" and j["geri_alma_dakika"] == 7 and j["azaldi_esigi"] == 2
    r = await istemci.put(URL, headers=yonetici, json={
        "ad": " Yeni Ad ", "telefon": "", "eposta": "bilgi@kulup.com", "adres": "Ankara", "azaldi_esigi": 4,
    })
    j = r.json()
    assert j == {"ad": "Yeni Ad", "telefon": None, "eposta": "bilgi@kulup.com", "adres": "Ankara",
                 "geri_alma_dakika": 7, "azaldi_esigi": 4}
    assert (await istemci.get(URL, headers=yonetici)).json() == j


async def test_dogrulama_422(istemci, yonetici):
    for govde in (
        {"geri_alma_dakika": 0}, {"geri_alma_dakika": 16}, {"azaldi_esigi": 0}, {"azaldi_esigi": 6},
        {"geri_alma_dakika": None}, {"ad": "A"}, {"ad": None}, {"telefon": "123"}, {"eposta": "yanlis"},
        {"bilinmeyen": 1},
    ):
        r = await istemci.put(URL, headers=yonetici, json=govde)
        assert r.status_code == 422, govde
    assert (await istemci.get(URL, headers=yonetici)).json()["geri_alma_dakika"] == 3


async def test_yetki(istemci):
    assert (await istemci.get(URL)).status_code == 401
    assert (await istemci.put(URL, json={"azaldi_esigi": 3})).status_code == 401
    for rol, eposta in ((Rol.antrenor, "a@kulup.com"), (Rol.veli, "v@kulup.com")):
        baslik = await giris(istemci, eposta, rol)
        assert (await istemci.get(URL, headers=baslik)).status_code == 403
        assert (await istemci.put(URL, headers=baslik, json={"azaldi_esigi": 3})).status_code == 403


async def test_denetim_yalniz_degisen_alanlar(istemci, yonetici):
    await istemci.put(URL, headers=yonetici, json={"adres": "Ankara", "azaldi_esigi": 2, "telefon": "5321234567"})
    await istemci.put(URL, headers=yonetici, json={"adres": "Ankara"})  # değişiklik yok
    async with SessionLocal() as s:
        kayitlar = list((await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ayar_guncellendi"))).scalars())
    assert len(kayitlar) == 1
    assert sorted(kayitlar[0].detay["alanlar"]) == ["adres", "telefon"]
    assert "5321234567" not in str(kayitlar[0].detay)


async def test_geri_alma_suresi_kuyruga_yansir(istemci, yonetici):
    await istemci.put(URL, headers=yonetici, json={"geri_alma_dakika": 10})
    o, _, _ = await ortam()
    await isaretle(o, await oturum(), YoklamaDurum.gelmedi)
    liste = await bildirimler("ders_gelmedi")
    assert liste and all(b.planli_zaman == T0 + timedelta(minutes=10) for b in liste)
    async with SessionLocal() as s:
        assert (await bsvc.ayarlari_oku(s)) == (timedelta(minutes=10), 2)


async def test_azaldi_esigi_kuyruga_yansir(istemci, yonetici):
    await istemci.put(URL, headers=yonetici, json={"azaldi_esigi": 3})
    o, _, _ = await ortam()
    await yukle(o, 4)
    await isaretle(o, await oturum(), YoklamaDurum.geldi)  # bakiye 3 = eşik
    assert len(await bildirimler("ders_hakki_azaldi")) == 2
    assert [b.parametreler for b in await bildirimler("ders_hakki_azaldi")][0] == {"bakiye": 3}


async def test_varsayilan_esik_ayarsiz_calisir():
    async with SessionLocal() as s:
        assert await s.get(KulupAyari, 1) is None
        assert await bsvc.ayarlari_oku(s) == (bsvc.GERI_ALMA_SURESI, bsvc.AZALDI_ESIGI)


async def test_iletisim_her_girisli_kullaniciya_acik(istemci, yonetici):
    await istemci.put(URL, headers=yonetici, json={"telefon": "0532 123 45 67", "eposta": "bilgi@kulup.com", "adres": "Ankara"})
    beklenen = {"ad": "Rota Performans Akademi", "telefon": "+905321234567", "eposta": "bilgi@kulup.com", "adres": "Ankara"}
    for rol, eposta in ((Rol.antrenor, "a@kulup.com"), (Rol.veli, "v@kulup.com")):
        baslik = await giris(istemci, eposta, rol)
        r = await istemci.get(f"{URL}/iletisim", headers=baslik)
        assert r.status_code == 200 and r.json() == beklenen
    assert (await istemci.get(f"{URL}/iletisim")).status_code == 401
