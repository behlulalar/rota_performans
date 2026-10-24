import io
import uuid
from datetime import date

import pytest
from PIL import Image
from sqlalchemy import select, text

from app import kimlik
from app.config import settings
from app.db import SessionLocal
from app.models import DenetimKaydi, IletisimKisisi, Ogrenci, Rol
from tests.conftest import SIFRE, kullanici_olustur

GECERLI_TC = "10000000146"
IKINCI_TC = "10000001068"


@pytest.fixture(autouse=True)
def gecici_dizin(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "dosya_dizini", str(tmp_path / "yuklemeler"))


async def giris(istemci, eposta, rol):
    await kullanici_olustur(eposta, rol)
    yanit = await istemci.post("/api/auth/login", json={"giris": eposta, "sifre": SIFRE})
    return {"Authorization": f"Bearer {yanit.json()['access_token']}"}


@pytest.fixture
async def yonetici(istemci):
    return await giris(istemci, "yonetici@kulup.com", Rol.admin)


def govde(**ek):
    temel = {
        "ad": "Deneme",
        "soyad": "Öğrenci",
        "dogum_tarihi": "2015-05-10",
        "kimlik_tur": "tc",
        "kimlik_no": GECERLI_TC,
        "iletisim_kisileri": [
            {"rol": "anne", "ad_soyad": "Deneme Anne", "telefon": "0 (532) 000-00 01", "birincil": True},
            {"rol": "diger", "ad_soyad": "Deneme Yakın", "telefon": "05320000002", "birincil": False},
        ],
        "rizalar": {"aydinlatma": True, "foto": True, "whatsapp": True},
    }
    temel.update(ek)
    return temel


async def olustur(istemci, baslik, **ek):
    yanit = await istemci.post("/api/ogrenciler", json=govde(**ek), headers=baslik)
    assert yanit.status_code == 201, yanit.text
    return yanit.json()


def resim_baytlari(bicim="JPEG", boyut=(1200, 600), exif=False):
    resim = Image.new("RGB", boyut, (200, 30, 30))
    cikti = io.BytesIO()
    if exif:
        e = Image.Exif()
        e[0x010F] = "GizliMarka"
        e[0x0112] = 6  # 90 derece döndür
        resim.save(cikti, bicim, exif=e)
    else:
        resim.save(cikti, bicim)
    return cikti.getvalue()


def foto_dosya(veri, ad="a.jpg", tip="image/jpeg"):
    return {"dosya": (ad, veri, tip)}


async def test_olusturma_ve_sifreli_saklama(istemci, yonetici):
    d = await olustur(istemci, yonetici)
    assert d["kimlik_maskeli"] == "100******46"
    assert d["durum"] == "aktif"
    assert d["birincil_iletisim"]["telefon"] == "05320000001"
    assert sorted(r["tur"] for r in d["rizalar"]) == ["aydinlatma", "foto", "whatsapp"]
    birincil = next(k for k in d["iletisim_kisileri"] if k["birincil"])
    assert birincil["whatsapp_izni"] is True

    async with SessionLocal() as s:
        o = await s.get(Ogrenci, uuid.UUID(d["id"]))
        assert o.kimlik_no_sifreli is not None and GECERLI_TC.encode() not in o.kimlik_no_sifreli
        assert o.kimlik_no_ozet != GECERLI_TC
        satir = (await s.execute(text("SELECT count(*) FROM ogrenci WHERE kimlik_no_ozet = :n"), {"n": GECERLI_TC})).scalar()
        assert satir == 0
        assert kimlik.coz(o.kimlik_no_sifreli) == GECERLI_TC
        denetim = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ogrenci_olusturuldu"))).scalar_one()
        assert denetim.hedef_id == d["id"] and denetim.detay is None


async def test_gecersiz_tc_422(istemci, yonetici):
    y = await istemci.post("/api/ogrenciler", json=govde(kimlik_no="12345678901"), headers=yonetici)
    assert y.status_code == 422
    assert y.json()["detail"] == "Geçersiz T.C. kimlik numarası"


async def test_pasaport(istemci, yonetici):
    y = await istemci.post("/api/ogrenciler", json=govde(kimlik_tur="pasaport", kimlik_no="ab1"), headers=yonetici)
    assert y.status_code == 422
    d = await olustur(istemci, yonetici, kimlik_tur="pasaport", kimlik_no="u12345678")
    assert d["kimlik_tur"] == "pasaport"


async def test_tekrar_tc_409(istemci, yonetici):
    await olustur(istemci, yonetici)
    y = await istemci.post("/api/ogrenciler", json=govde(), headers=yonetici)
    assert y.status_code == 409
    assert y.json()["detail"] == "Bu kimlik numarasıyla kayıtlı bir öğrenci var"


@pytest.mark.parametrize("birincil", [(False, False), (True, True)])
async def test_birincil_sayisi_422(istemci, yonetici, birincil):
    kisiler = [
        {"rol": "anne", "ad_soyad": "A", "telefon": "05320000001", "birincil": birincil[0]},
        {"rol": "diger", "ad_soyad": "B", "telefon": "05320000002", "birincil": birincil[1]},
    ]
    y = await istemci.post("/api/ogrenciler", json=govde(iletisim_kisileri=kisiler), headers=yonetici)
    assert y.status_code == 422


async def test_diger_veya_kendisi_zorunlu(istemci, yonetici):
    kisiler = [
        {"rol": "anne", "ad_soyad": "A", "telefon": "05320000001", "birincil": True},
        {"rol": "baba", "ad_soyad": "B", "telefon": "05320000002", "birincil": False},
    ]
    y = await istemci.post("/api/ogrenciler", json=govde(iletisim_kisileri=kisiler), headers=yonetici)
    assert y.status_code == 422
    kisiler[1]["rol"] = "kendisi"
    y = await istemci.post("/api/ogrenciler", json=govde(iletisim_kisileri=kisiler), headers=yonetici)
    assert y.status_code == 201


async def test_liste_arama_filtre_sayfalama(istemci, yonetici):
    tcler = [GECERLI_TC, IKINCI_TC, None]
    for ad, soyad, tc in zip(["Ayşe", "Mehmet", "Ali"], ["Yılmaz", "Kaya", "Demir"], tcler):
        await olustur(istemci, yonetici, ad=ad, soyad=soyad, kimlik_no=tc)
    async with SessionLocal() as s:
        s.add(Ogrenci(ad="Sahte", soyad="Kayıt", dogum_tarihi=date(2015, 1, 1), sentetik=True))
        await s.commit()

    y = (await istemci.get("/api/ogrenciler", headers=yonetici)).json()
    assert y["toplam"] == 3 and y["sayfa"] == 1 and y["boyut"] == 25
    assert [k["soyad"] for k in y["kayitlar"]] == ["Demir", "Kaya", "Yılmaz"]
    assert y["kayitlar"][2]["kimlik_maskeli"] == "100******46"
    assert y["kayitlar"][0]["kimlik_maskeli"] is None
    assert y["kayitlar"][0]["foto_var"] is False

    y = (await istemci.get("/api/ogrenciler?q=kAYa", headers=yonetici)).json()
    assert y["toplam"] == 1 and y["kayitlar"][0]["ad"] == "Mehmet"
    y = (await istemci.get("/api/ogrenciler?q=100%25", headers=yonetici)).json()
    assert y["toplam"] == 0

    sayfa2 = (await istemci.get("/api/ogrenciler?sayfa=2&boyut=2", headers=yonetici)).json()
    assert sayfa2["toplam"] == 3 and len(sayfa2["kayitlar"]) == 1

    ogr = (await istemci.get("/api/ogrenciler?q=Ali", headers=yonetici)).json()["kayitlar"][0]
    await istemci.post(f"/api/ogrenciler/{ogr['id']}/pasife-al", headers=yonetici)
    assert (await istemci.get("/api/ogrenciler?durum=pasif", headers=yonetici)).json()["toplam"] == 1
    assert (await istemci.get("/api/ogrenciler?durum=aktif", headers=yonetici)).json()["toplam"] == 2
    assert (await istemci.get("/api/ogrenciler?boyut=101", headers=yonetici)).status_code == 422


async def test_detay_uyarilari(istemci, yonetici):
    kucuk = await olustur(istemci, yonetici, dogum_tarihi=date.today().replace(year=date.today().year - 3).isoformat())
    assert kucuk["uyarilar"] == ["Öğrenci 5 yaşını doldurmamış"]
    resit = await olustur(
        istemci, yonetici, kimlik_no=IKINCI_TC,
        dogum_tarihi=date.today().replace(year=date.today().year - 20).isoformat(),
    )
    assert resit["uyarilar"] == ["Öğrenci reşit, birincil iletişim kişisi kendisi olmalı"]
    d = (await istemci.get(f"/api/ogrenciler/{resit['id']}", headers=yonetici)).json()
    assert d["uyarilar"] == resit["uyarilar"] and d["yas"] == 20
    assert d["kayit_tarihi"]
    normal = await olustur(istemci, yonetici, kimlik_no=None)
    assert normal["uyarilar"] == []


async def test_bulunamadi(istemci, yonetici):
    y = await istemci.get(f"/api/ogrenciler/{uuid.uuid4()}", headers=yonetici)
    assert y.status_code == 404 and y.json()["detail"] == "Öğrenci bulunamadı"


async def test_kimlik_goruntuleme_denetim(istemci, yonetici):
    d = await olustur(istemci, yonetici)
    for _ in range(2):
        y = await istemci.get(f"/api/ogrenciler/{d['id']}/kimlik", headers=yonetici)
        assert y.json() == {"kimlik_no": GECERLI_TC}
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "kimlik_goruntulendi"))).scalars().all()
        assert len(kayitlar) == 2 and kayitlar[0].hedef_id == d["id"]
        assert GECERLI_TC not in str(kayitlar[0].detay)
    bos = await olustur(istemci, yonetici, kimlik_no=None)
    assert (await istemci.get(f"/api/ogrenciler/{bos['id']}/kimlik", headers=yonetici)).status_code == 404


async def test_guncelleme(istemci, yonetici):
    a = await olustur(istemci, yonetici)
    b = await olustur(istemci, yonetici, kimlik_no=IKINCI_TC)
    y = await istemci.patch(f"/api/ogrenciler/{a['id']}", json={"ad": "Yeni", "cinsiyet": "kadin"}, headers=yonetici)
    assert y.status_code == 200 and y.json()["ad"] == "Yeni" and y.json()["cinsiyet"] == "kadin"
    assert y.json()["soyad"] == "Öğrenci"
    assert (await istemci.patch(f"/api/ogrenciler/{a['id']}", json={"kimlik_no": IKINCI_TC}, headers=yonetici)).status_code == 422
    r = await istemci.patch(f"/api/ogrenciler/{a['id']}", json={"kimlik_tur": "tc", "kimlik_no": IKINCI_TC}, headers=yonetici)
    assert r.status_code == 409
    r = await istemci.patch(f"/api/ogrenciler/{a['id']}", json={"kimlik_tur": "tc", "kimlik_no": "11111111111"}, headers=yonetici)
    assert r.status_code == 422
    r = await istemci.patch(f"/api/ogrenciler/{b['id']}", json={"kimlik_tur": "tc", "kimlik_no": IKINCI_TC}, headers=yonetici)
    assert r.status_code == 200
    async with SessionLocal() as s:
        assert (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ogrenci_guncellendi"))).scalars().first()


async def test_pasife_al_aktif_et(istemci, yonetici):
    d = await olustur(istemci, yonetici)
    assert (await istemci.post(f"/api/ogrenciler/{d['id']}/pasife-al", headers=yonetici)).json()["durum"] == "pasif"
    assert (await istemci.post(f"/api/ogrenciler/{d['id']}/aktif-et", headers=yonetici)).json()["durum"] == "aktif"
    async with SessionLocal() as s:
        islemler = {k.islem for k in (await s.execute(select(DenetimKaydi))).scalars()}
        assert {"ogrenci_pasife_alindi", "ogrenci_aktif_edildi"} <= islemler


async def test_iletisim_kisilerini_degistirme(istemci, yonetici):
    d = await olustur(istemci, yonetici)
    yeni = [
        {"rol": "baba", "ad_soyad": "Yeni Baba", "telefon": "+90 532 000 00 09", "birincil": True},
        {"rol": "kendisi", "ad_soyad": "Deneme", "telefon": "05320000003", "birincil": False},
    ]
    y = await istemci.put(f"/api/ogrenciler/{d['id']}/iletisim-kisileri", json=yeni, headers=yonetici)
    assert y.status_code == 200
    kisiler = y.json()["iletisim_kisileri"]
    assert len(kisiler) == 2 and y.json()["birincil_iletisim"]["telefon"] == "+905320000009"
    assert next(k for k in kisiler if k["birincil"])["whatsapp_izni"] is True
    # kurallar
    for kotu in (
        [{**yeni[0], "birincil": False}, yeni[1]],
        [yeni[0], {**yeni[1], "birincil": True}],
        [yeni[0], {**yeni[1], "rol": "anne"}],
        [{**yeni[0], "telefon": "abc"}, yeni[1]],
    ):
        assert (await istemci.put(f"/api/ogrenciler/{d['id']}/iletisim-kisileri", json=kotu, headers=yonetici)).status_code == 422


async def test_hesapli_birincil_degistirilemez(istemci, yonetici):
    d = await olustur(istemci, yonetici)
    veli = await kullanici_olustur("veli@kulup.com", Rol.veli)
    async with SessionLocal() as s:
        b = (await s.execute(select(IletisimKisisi).where(IletisimKisisi.birincil))).scalar_one()
        b.kullanici_id = veli.id
        await s.commit()
    kisiler = d["iletisim_kisileri"]
    # Birincillik diğer kişiye geçiyor.
    gecis = [
        {"id": k["id"], "rol": k["rol"], "ad_soyad": k["ad_soyad"], "telefon": k["telefon"], "birincil": not k["birincil"]}
        for k in kisiler
    ]
    y = await istemci.put(f"/api/ogrenciler/{d['id']}/iletisim-kisileri", json=gecis, headers=yonetici)
    assert y.status_code == 409
    assert y.json()["detail"] == "Hesabı olan birincil kişi değiştirilemez (hesap devri henüz desteklenmiyor)"
    # Aynı kişi birincil kalırsa (telefon güncellenir) hesap bağı korunur.
    ayni = [
        {"id": k["id"], "rol": k["rol"], "ad_soyad": k["ad_soyad"],
         "telefon": "05329999999" if k["birincil"] else k["telefon"], "birincil": k["birincil"]}
        for k in kisiler
    ]
    assert (await istemci.put(f"/api/ogrenciler/{d['id']}/iletisim-kisileri", json=ayni, headers=yonetici)).status_code == 200
    async with SessionLocal() as s:
        b = (await s.execute(select(IletisimKisisi).where(IletisimKisisi.birincil))).scalar_one()
        assert b.kullanici_id == veli.id and b.telefon == "05329999999"


@pytest.mark.parametrize("rol", [Rol.antrenor, Rol.veli])
async def test_yetkisiz_roller_403(istemci, rol):
    baslik = await giris(istemci, "x@kulup.com", rol)
    await istemci.post("/api/ogrenciler", json=govde())  # 401, kayıt oluşmaz
    for yontem, yol, kw in uclar():
        y = await istemci.request(yontem, yol, headers=baslik, **kw)
        assert y.status_code == 403, (yontem, yol, y.status_code)


async def test_belirtecsiz_401(istemci):
    for yontem, yol, kw in uclar():
        y = await istemci.request(yontem, yol, **kw)
        assert y.status_code == 401, (yontem, yol, y.status_code)


def uclar():
    i = str(uuid.uuid4())
    b = f"/api/ogrenciler/{i}"
    return [
        ("GET", "/api/ogrenciler", {}),
        ("POST", "/api/ogrenciler", {"json": govde()}),
        ("GET", b, {}),
        ("PATCH", b, {"json": {"ad": "X"}}),
        ("PUT", b + "/iletisim-kisileri", {"json": govde()["iletisim_kisileri"]}),
        ("POST", b + "/pasife-al", {}),
        ("POST", b + "/aktif-et", {}),
        ("GET", b + "/kimlik", {}),
        ("POST", b + "/foto", {"files": foto_dosya(resim_baytlari())}),
        ("GET", b + "/foto", {}),
        ("DELETE", b + "/foto", {}),
    ]


async def test_foto_rizasiz_409(istemci, yonetici):
    d = await olustur(istemci, yonetici, rizalar={"aydinlatma": True, "foto": False, "whatsapp": False})
    y = await istemci.post(f"/api/ogrenciler/{d['id']}/foto", files=foto_dosya(resim_baytlari()), headers=yonetici)
    assert y.status_code == 409 and y.json()["detail"] == "Fotoğraf için veli rızası yok"


async def test_foto_yukleme_isleme_ve_getirme(istemci, yonetici, tmp_path):
    d = await olustur(istemci, yonetici)
    url = f"/api/ogrenciler/{d['id']}/foto"
    assert (await istemci.get(url, headers=yonetici)).status_code == 404
    y = await istemci.post(url, files=foto_dosya(resim_baytlari(exif=True)), headers=yonetici)
    assert y.status_code == 204

    buyuk = await istemci.get(url + "?boyut=buyuk", headers=yonetici)
    kucuk = await istemci.get(url, headers=yonetici)
    assert buyuk.headers["content-type"] == "image/jpeg"
    assert buyuk.headers["cache-control"] == "private, max-age=86400"
    assert buyuk.headers["etag"]
    gb, gk = Image.open(io.BytesIO(buyuk.content)), Image.open(io.BytesIO(kucuk.content))
    # EXIF yönü 6: 1200x600 resim dik (600x1200) olur, sonra en uzun kenar 800'e iner.
    assert gb.size == (400, 800)
    assert gk.size == (160, 160)
    for g in (gb, gk):
        assert len(g.getexif()) == 0 and "exif" not in g.info and "icc_profile" not in g.info
    assert b"GizliMarka" not in buyuk.content

    ikinci = await istemci.get(url + "?boyut=buyuk", headers={**yonetici, "If-None-Match": buyuk.headers["etag"]})
    assert ikinci.status_code == 304
    assert (await istemci.get(url + "?boyut=dev", headers=yonetici)).status_code == 422

    liste = (await istemci.get("/api/ogrenciler", headers=yonetici)).json()["kayitlar"][0]
    assert liste["foto_var"] is True

    # dosya adı rastgele hex, öğrenci adı yok
    dosyalar = sorted(p.name for p in (tmp_path / "yuklemeler").iterdir())
    assert len(dosyalar) == 2 and all("deneme" not in n.lower() for n in dosyalar)

    # yeni yükleme eskisini siler
    await istemci.post(url, files=foto_dosya(resim_baytlari("PNG"), "a.png", "image/png"), headers=yonetici)
    assert len(list((tmp_path / "yuklemeler").iterdir())) == 2
    assert (await istemci.get(url, headers=yonetici)).headers["etag"] != kucuk.headers["etag"]

    assert (await istemci.delete(url, headers=yonetici)).status_code == 204
    assert list((tmp_path / "yuklemeler").iterdir()) == []
    assert (await istemci.get(url, headers=yonetici)).status_code == 404


async def test_foto_webp_kabul(istemci, yonetici):
    d = await olustur(istemci, yonetici)
    y = await istemci.post(
        f"/api/ogrenciler/{d['id']}/foto", files=foto_dosya(resim_baytlari("WEBP"), "a.webp", "image/webp"),
        headers=yonetici,
    )
    assert y.status_code == 204


async def test_foto_gecersiz_ve_buyuk(istemci, yonetici):
    d = await olustur(istemci, yonetici)
    url = f"/api/ogrenciler/{d['id']}/foto"
    y = await istemci.post(url, files=foto_dosya(b"bu bir resim degil", "a.jpg"), headers=yonetici)
    assert y.status_code == 422
    # uzantı jpg olsa da içerik GIF ise reddedilir
    y = await istemci.post(url, files=foto_dosya(resim_baytlari("GIF"), "a.jpg"), headers=yonetici)
    assert y.status_code == 422
    y = await istemci.post(url, files=foto_dosya(b"\0" * (8 * 1024 * 1024 + 1)), headers=yonetici)
    assert y.status_code == 413
    assert (await istemci.get(url, headers=yonetici)).status_code == 404


def test_depolama_yol_gecisi_engeli():
    from app.depolama import DepolamaHatasi, depolama

    for kotu in ("../etc/passwd", "ABC", "a" * 31, "../" + "a" * 29):
        with pytest.raises(DepolamaHatasi):
            depolama.oku(kotu, "kucuk")


async def test_yalnizca_bosluktan_olusan_ad_reddedilir(istemci):
    await kullanici_olustur()
    yanit = await istemci.post("/api/auth/login", json={"giris": "yonetici@kulup.com", "sifre": SIFRE})
    bas = {"Authorization": f"Bearer {yanit.json()['access_token']}"}
    govde = {
        "ad": "   ", "soyad": "Deneme", "dogum_tarihi": "2016-01-03", "kimlik_tur": "tc",
        "iletisim_kisileri": [{"rol": "diger", "ad_soyad": "Kişi", "telefon": "05551112233", "birincil": True}],
        "rizalar": {"aydinlatma": True, "foto": False, "whatsapp": False},
    }
    assert (await istemci.post("/api/ogrenciler", json=govde, headers=bas)).status_code == 422
    govde["ad"] = "Ada"
    olusan = (await istemci.post("/api/ogrenciler", json=govde, headers=bas)).json()
    guncelle = await istemci.patch(f"/api/ogrenciler/{olusan['id']}", json={"ad": "  "}, headers=bas)
    assert guncelle.status_code == 422
