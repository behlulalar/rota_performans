import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DenetimKaydi, IletisimKisisi, Kullanici, Ogrenci, Oturum, Rol
from app.api.auth import COOKIE_ADI, COOKIE_YOLU
from tests.conftest import SIFRE, kullanici_olustur
from tests.test_ogrenciler import giris as yonetici_girisi

TELEFON = "0555 111 22 33"
SADE = "+905551112233"


@pytest.fixture
async def yonetici(istemci):
    return await yonetici_girisi(istemci, "yonetici@kulup.com", Rol.admin)


def dogum(yas: int, gun_once: int = 0) -> str:
    """Bugün tam `yas` yaşında olan (gun_once kadar gün önce doğmuş gibi değil, tam bugün) bir tarih."""
    b = date.today()
    try:
        d = b.replace(year=b.year - yas)
    except ValueError:  # 29 Şubat
        d = b.replace(year=b.year - yas, day=28)
    return d.isoformat()


def ertesi_gun_dogum(yas: int) -> str:
    """Yarın `yas` yaşını dolduracak, yani bugün hâlâ yas-1 yaşında olan tarih."""
    from datetime import timedelta

    d = date.fromisoformat(dogum(yas)) + timedelta(days=1)
    return d.isoformat()


_sayac = 0


async def ogrenci_ac(istemci, baslik, *, yas=10, rol="anne", telefon=TELEFON, dogum_tarihi=None, ad="Ali"):
    global _sayac
    _sayac += 1
    dt = dogum_tarihi or dogum(yas)
    resit = date.fromisoformat(dt) <= date.fromisoformat(dogum(18))
    # Reşit öğrenci artık kayıtta kendi telefonuyla ve otomatik "kendisi" birincille açılır.
    # Reşit + veli birincil durumu, eski kayıtların yaşlanması gibi, doğum tarihi sonradan güncellenerek kurulur.
    kisiler = [{"rol": rol, "ad_soyad": "Kişi Bir", "telefon": telefon, "birincil": True}]
    if resit and rol == "kendisi":
        kisiler = []
    if rol not in ("diger", "kendisi"):
        kisiler.append({"rol": "diger", "ad_soyad": "Diğer", "telefon": "05320000009", "birincil": False})
    govde = {
        "ad": ad,
        "soyad": f"Soy{_sayac}",
        "dogum_tarihi": dogum(10) if resit and rol != "kendisi" else dt,
        "kimlik_tur": "pasaport",
        "kimlik_no": f"AB{_sayac:06d}",
        "iletisim_kisileri": kisiler,
        "rizalar": {"aydinlatma": True, "foto": False, "whatsapp": True},
    }
    if resit and rol == "kendisi":
        govde["telefon"] = telefon
    y = await istemci.post("/api/ogrenciler", json=govde, headers=baslik)
    assert y.status_code == 201, y.text
    if resit and rol != "kendisi":
        g = await istemci.patch(f"/api/ogrenciler/{y.json()['id']}", json={"dogum_tarihi": dt}, headers=baslik)
        assert g.status_code == 200, g.text
        return g.json()
    return y.json()


async def hesap_ac(istemci, baslik, oid, **govde):
    return await istemci.post(f"/api/ogrenciler/{oid}/hesap", json=govde, headers=baslik)


async def login(istemci, giris, sifre):
    return await istemci.post("/api/auth/login", json={"giris": giris, "sifre": sifre})


async def test_veli_hesabi_ac_ve_telefonla_giris(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici)
    y = await hesap_ac(istemci, yonetici, o["id"])
    assert y.status_code == 200, y.text
    d = y.json()
    assert d["giris"] == SADE and d["yeni_hesap"] is True and d["gecici_sifre"]
    assert (await login(istemci, TELEFON, d["gecici_sifre"])).status_code == 200
    assert (await login(istemci, SADE, d["gecici_sifre"])).status_code == 200
    detay = (await istemci.get(f"/api/ogrenciler/{o['id']}", headers=yonetici)).json()
    assert detay["hesap"] == {"giris": SADE, "rol": "veli", "aktif": True, "bagli_ogrenci_sayisi": 1}


async def test_kardeste_ayni_hesaba_baglanir(istemci, yonetici):
    a = await ogrenci_ac(istemci, yonetici)
    b = await ogrenci_ac(istemci, yonetici, ad="Veli")
    ilk = (await hesap_ac(istemci, yonetici, a["id"])).json()
    y = await hesap_ac(istemci, yonetici, b["id"])
    assert y.status_code == 200
    assert y.json()["gecici_sifre"] is None and y.json()["yeni_hesap"] is False
    detay = (await istemci.get(f"/api/ogrenciler/{b['id']}", headers=yonetici)).json()
    assert detay["hesap"]["bagli_ogrenci_sayisi"] == 2
    async with SessionLocal() as s:
        idler = {k.kullanici_id for k in (await s.execute(select(IletisimKisisi))).scalars() if k.kullanici_id}
        assert len(idler) == 1
    assert (await login(istemci, SADE, ilk["gecici_sifre"])).status_code == 200


async def test_rol_uyumsuz_giris_409(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici)
    await kullanici_olustur("antrenor@kulup.com", Rol.antrenor)
    y = await hesap_ac(istemci, yonetici, o["id"], giris="Antrenor@Kulup.com")
    assert y.status_code == 409
    assert y.json()["detail"] == "Bu giriş bilgisi başka türde bir hesapta kayıtlı"


async def test_gecersiz_eposta_422_ve_eposta_ile_acma(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici)
    assert (await hesap_ac(istemci, yonetici, o["id"], giris="a@b")).status_code == 422
    y = await hesap_ac(istemci, yonetici, o["id"], giris=" Veli@Ornek.com ")
    assert y.status_code == 200 and y.json()["giris"] == "veli@ornek.com"


async def test_tekrar_acma_409(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici)
    assert (await hesap_ac(istemci, yonetici, o["id"])).status_code == 200
    y = await hesap_ac(istemci, yonetici, o["id"])
    assert y.status_code == 409
    assert y.json()["detail"] == "Bu öğrencinin panel hesabı zaten var"


async def test_birincil_yok_ve_pasif_ogrenci_422(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici)
    async with SessionLocal() as s:
        for k in (await s.execute(select(IletisimKisisi).where(IletisimKisisi.ogrenci_id == uuid.UUID(o["id"])))).scalars():
            await s.delete(k)
        await s.commit()
    assert (await hesap_ac(istemci, yonetici, o["id"])).status_code == 422
    p = await ogrenci_ac(istemci, yonetici)
    await istemci.post(f"/api/ogrenciler/{p['id']}/pasife-al", headers=yonetici)
    assert (await hesap_ac(istemci, yonetici, p["id"])).status_code == 422


async def test_hesap_ayirma_kardes_ve_son_bag(istemci, yonetici):
    a = await ogrenci_ac(istemci, yonetici)
    b = await ogrenci_ac(istemci, yonetici)
    sifre = (await hesap_ac(istemci, yonetici, a["id"])).json()["gecici_sifre"]
    await hesap_ac(istemci, yonetici, b["id"])
    yanit = await login(istemci, SADE, sifre)
    yenileme = yanit.cookies.get(COOKIE_ADI)
    assert yenileme

    y = await istemci.delete(f"/api/ogrenciler/{a['id']}/hesap", headers=yonetici)
    assert y.status_code == 200 and y.json()["hesap"] is None
    detay_b = (await istemci.get(f"/api/ogrenciler/{b['id']}", headers=yonetici)).json()
    assert detay_b["hesap"]["aktif"] is True and detay_b["hesap"]["bagli_ogrenci_sayisi"] == 1
    assert (await login(istemci, SADE, sifre)).status_code == 200

    y = await istemci.delete(f"/api/ogrenciler/{b['id']}/hesap", headers=yonetici)
    assert y.status_code == 200
    async with SessionLocal() as s:
        k = (await s.execute(select(Kullanici).where(Kullanici.giris == SADE))).scalar_one()
        assert k.aktif is False
        oturumlar = (await s.execute(select(Oturum).where(Oturum.kullanici_id == k.id))).scalars().all()
        assert oturumlar and all(o.iptal for o in oturumlar)
    assert (await login(istemci, SADE, sifre)).status_code == 401
    istemci.cookies.clear()
    istemci.cookies.set(COOKIE_ADI, yenileme, path=COOKIE_YOLU)
    assert (await istemci.post("/api/auth/refresh")).status_code == 401
    # Hesap yokken tekrar ayırma 404
    assert (await istemci.delete(f"/api/ogrenciler/{b['id']}/hesap", headers=yonetici)).status_code == 404


async def test_sifre_sifirlama(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici)
    assert (await istemci.post(f"/api/ogrenciler/{o['id']}/hesap/sifre-sifirla", headers=yonetici)).status_code == 404
    eski = (await hesap_ac(istemci, yonetici, o["id"])).json()["gecici_sifre"]
    y = await istemci.post(f"/api/ogrenciler/{o['id']}/hesap/sifre-sifirla", headers=yonetici)
    assert y.status_code == 200
    yeni = y.json()["gecici_sifre"]
    assert yeni != eski
    assert (await login(istemci, SADE, eski)).status_code == 401
    assert (await login(istemci, SADE, yeni)).status_code == 200


async def test_kendisi_birincilken_ogrenci_rolu(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici, yas=20, rol="kendisi")
    y = await hesap_ac(istemci, yonetici, o["id"])
    assert y.status_code == 200
    detay = (await istemci.get(f"/api/ogrenciler/{o['id']}", headers=yonetici)).json()
    assert detay["hesap"]["rol"] == "ogrenci"
    async with SessionLocal() as s:
        og = await s.get(Ogrenci, uuid.UUID(o["id"]))
        k = (await s.execute(select(Kullanici).where(Kullanici.giris == SADE))).scalar_one()
        assert og.kullanici_id == k.id
    # Öğrenci hesabı başka bir öğrenciye bağlanamaz
    diger = await ogrenci_ac(istemci, yonetici, yas=21, rol="kendisi")
    assert (await hesap_ac(istemci, yonetici, diger["id"])).status_code == 409


async def test_resit_uyarilari(istemci, yonetici):
    on_yedi = await ogrenci_ac(istemci, yonetici, dogum_tarihi=ertesi_gun_dogum(18))
    on_sekiz = await ogrenci_ac(istemci, yonetici, dogum_tarihi=dogum(18))
    kendisi = await ogrenci_ac(istemci, yonetici, yas=25, rol="kendisi")
    pasif = await ogrenci_ac(istemci, yonetici, yas=30)
    await istemci.post(f"/api/ogrenciler/{pasif['id']}/pasife-al", headers=yonetici)
    await hesap_ac(istemci, yonetici, on_sekiz["id"])
    y = await istemci.get("/api/ogrenciler/resit-uyarilari", headers=yonetici)
    assert y.status_code == 200
    liste = {u["id"]: u for u in y.json()}
    assert set(liste) == {on_sekiz["id"]}
    assert liste[on_sekiz["id"]]["yas"] == 18
    assert liste[on_sekiz["id"]]["birincil_rol"] == "anne"
    assert liste[on_sekiz["id"]]["veli_hesabi_var"] is True
    assert on_yedi["id"] not in liste and kendisi["id"] not in liste


async def test_resit_gecisi(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici, yas=19)
    veli_sifre = (await hesap_ac(istemci, yonetici, o["id"])).json()["gecici_sifre"]
    y = await istemci.post(
        f"/api/ogrenciler/{o['id']}/resit-gecisi", json={"telefon": "0532 999 88 77"}, headers=yonetici
    )
    assert y.status_code == 200, y.text
    d = y.json()
    assert d["hesap"] is None
    assert d["birincil_iletisim"]["rol"] == "kendisi" and d["birincil_iletisim"]["telefon"] == "+905329998877"
    assert d["birincil_iletisim"]["ad_soyad"] == f"{o['ad']} {o['soyad']}"
    assert sum(1 for k in d["iletisim_kisileri"] if k["birincil"]) == 1
    kendisi = next(k for k in d["iletisim_kisileri"] if k["rol"] == "kendisi")
    assert kendisi["whatsapp_izni"] is True
    assert (await login(istemci, SADE, veli_sifre)).status_code == 401  # eski veli hesabı pasif
    assert not d["uyarilar"]
    assert d["telefon"] == "+905329998877"  # kişisel bilgilerdeki telefon da iletişimle aynı

    h = await hesap_ac(istemci, yonetici, o["id"])
    assert h.status_code == 200 and h.json()["giris"] == "+905329998877"
    detay = (await istemci.get(f"/api/ogrenciler/{o['id']}", headers=yonetici)).json()
    assert detay["hesap"]["rol"] == "ogrenci"
    assert (await login(istemci, "05329998877", h.json()["gecici_sifre"])).status_code == 200


async def test_resit_gecisi_18_alti_422(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici, dogum_tarihi=ertesi_gun_dogum(18))
    y = await istemci.post(f"/api/ogrenciler/{o['id']}/resit-gecisi", json={"telefon": SADE}, headers=yonetici)
    assert y.status_code == 422


async def test_gecici_sifre_denetimde_yok(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici)
    sifre = (await hesap_ac(istemci, yonetici, o["id"])).json()["gecici_sifre"]
    yeni = (await istemci.post(f"/api/ogrenciler/{o['id']}/hesap/sifre-sifirla", headers=yonetici)).json()["gecici_sifre"]
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi))).scalars().all()
    islemler = {k.islem for k in kayitlar}
    assert {"panel_hesabi_acildi", "panel_hesabi_sifre_sifirlandi"} <= islemler
    metin = " ".join(f"{k.detay} {k.hedef_id}" for k in kayitlar)
    assert sifre not in metin and yeni not in metin and SADE not in metin


async def test_yetki(istemci, yonetici):
    o = await ogrenci_ac(istemci, yonetici)
    antrenor = await yonetici_girisi(istemci, "antrenor@kulup.com", Rol.antrenor)
    veli = await yonetici_girisi(istemci, "veli@kulup.com", Rol.veli)
    istekler = [
        ("post", f"/api/ogrenciler/{o['id']}/hesap", {}),
        ("delete", f"/api/ogrenciler/{o['id']}/hesap", None),
        ("post", f"/api/ogrenciler/{o['id']}/hesap/sifre-sifirla", None),
        ("get", "/api/ogrenciler/resit-uyarilari", None),
        ("post", f"/api/ogrenciler/{o['id']}/resit-gecisi", {"telefon": SADE}),
    ]
    for yontem, yol, json in istekler:
        for baslik, kod in ((antrenor, 403), (veli, 403), ({}, 401)):
            kw = {"headers": baslik}
            if json is not None:
                kw["json"] = json
            y = await getattr(istemci, yontem)(yol, **kw)
            assert y.status_code == kod, (yontem, yol, y.status_code)
