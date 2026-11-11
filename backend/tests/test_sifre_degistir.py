from sqlalchemy import select

from app.api.auth import COOKIE_ADI
from app.db import SessionLocal
from app.models import DenetimKaydi, Kullanici, Oturum, Rol
from app.security import sifre_ozeti
from tests.conftest import SIFRE, kullanici_olustur
from tests.test_ogrenciler import giris as yonetici_girisi
from tests.test_veli_hesaplari import ogrenci_ac

YENI = "Yeni-sifre-4567"
URL = "/api/auth/sifre-degistir"


async def bayrakli(giris="hoca@kulup.com", rol=Rol.antrenor):
    k = await kullanici_olustur(giris, rol)
    async with SessionLocal() as s:
        (await s.get(Kullanici, k.id)).sifre_degistirmeli = True
        await s.commit()
    return k


async def login(istemci, giris, sifre=SIFRE):
    y = await istemci.post("/api/auth/login", json={"giris": giris, "sifre": sifre})
    assert y.status_code == 200
    return {"Authorization": f"Bearer {y.json()['access_token']}"}


async def getir(giris):
    async with SessionLocal() as s:
        return (await s.execute(select(Kullanici).where(Kullanici.giris == giris))).scalar_one()


async def test_bayrakli_korumali_403_me_serbest(istemci):
    await bayrakli()
    # rol_gerekli de bayrağı uygular: yönetici bayraklıysa yönetici uç noktası 403 + başlık.
    await bayrakli("yonetici@kulup.com", Rol.admin)
    ha = await login(istemci, "yonetici@kulup.com")
    y = await istemci.get("/api/antrenorler", headers=ha)
    assert y.status_code == 403
    assert y.json()["detail"] == "Şifrenizi değiştirmeniz gerekiyor"
    assert y.headers["X-Hata-Kodu"] == "sifre_degistirmeli"
    me = await istemci.get("/api/auth/me", headers=ha)
    assert me.status_code == 200 and me.json()["sifre_degistirmeli"] is True


async def test_degistirince_acilir_ve_bayrak_kalkar(istemci):
    await bayrakli("yonetici@kulup.com", Rol.admin)
    h = await login(istemci, "yonetici@kulup.com")
    y = await istemci.post(URL, headers=h, json={"mevcut_sifre": SIFRE, "yeni_sifre": YENI})
    assert y.status_code == 204
    assert (await istemci.get("/api/antrenorler", headers=h)).status_code == 200
    me = await istemci.get("/api/auth/me", headers=h)
    assert me.json()["sifre_degistirmeli"] is False
    k = await getir("yonetici@kulup.com")
    assert k.sifre_degistirmeli is False
    await login(istemci, "yonetici@kulup.com", YENI)
    async with SessionLocal() as s:
        kayit = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "sifre_degistirildi"))).scalars().all()
    assert len(kayit) == 1 and YENI not in str(kayit[0].detay)


async def test_yanlis_mevcut_sifre_ve_kilit(istemci):
    await bayrakli("yonetici@kulup.com", Rol.admin)
    h = await login(istemci, "yonetici@kulup.com")
    for _ in range(4):
        y = await istemci.post(URL, headers=h, json={"mevcut_sifre": "yanlis-sifre-1", "yeni_sifre": YENI})
        assert y.status_code == 400
    assert (await getir("yonetici@kulup.com")).basarisiz_deneme == 4
    await istemci.post(URL, headers=h, json={"mevcut_sifre": "yanlis-sifre-1", "yeni_sifre": YENI})
    k = await getir("yonetici@kulup.com")
    assert k.kilit_bitis is not None and k.sifre_degistirmeli is True
    y = await istemci.post(URL, headers=h, json={"mevcut_sifre": SIFRE, "yeni_sifre": YENI})
    assert y.status_code == 401


async def test_zayif_ve_ayni_sifre_422(istemci):
    await bayrakli("yonetici@kulup.com", Rol.admin)
    h = await login(istemci, "yonetici@kulup.com")
    for yeni in ["kisa1", "sadeceharflerdir", "12345678901", "x" * 257, SIFRE]:
        y = await istemci.post(URL, headers=h, json={"mevcut_sifre": SIFRE, "yeni_sifre": yeni})
        assert y.status_code == 422, yeni
    assert (await getir("yonetici@kulup.com")).sifre_degistirmeli is True


async def test_giris_gerekli(istemci):
    y = await istemci.post(URL, json={"mevcut_sifre": SIFRE, "yeni_sifre": YENI})
    assert y.status_code == 401


async def test_diger_oturumlar_iptal_edilir_kendi_kalir(istemci):
    await bayrakli("yonetici@kulup.com", Rol.admin)
    # Diğer cihaz oturumu
    await login(istemci, "yonetici@kulup.com")
    diger = istemci.cookies.get(COOKIE_ADI)
    h = await login(istemci, "yonetici@kulup.com")  # istemci çerezi artık bu oturumun
    assert istemci.cookies.get(COOKIE_ADI) != diger
    y = await istemci.post(URL, headers=h, json={"mevcut_sifre": SIFRE, "yeni_sifre": YENI})
    assert y.status_code == 204
    async with SessionLocal() as s:
        oturumlar = (await s.execute(select(Oturum))).scalars().all()
    assert sorted(o.iptal for o in oturumlar) == [False, True]
    assert (await istemci.post("/api/auth/refresh")).status_code == 200


async def test_cerezsiz_hepsi_iptal(istemci):
    await bayrakli("yonetici@kulup.com", Rol.admin)
    h = await login(istemci, "yonetici@kulup.com")
    istemci.cookies.clear()
    y = await istemci.post(URL, headers=h, json={"mevcut_sifre": SIFRE, "yeni_sifre": YENI})
    assert y.status_code == 204
    async with SessionLocal() as s:
        assert all(o.iptal for o in (await s.execute(select(Oturum))).scalars().all())


async def test_admin_bayraksiz_ve_gecici_sifre_uretenler_bayrak_koyar(istemci):
    h = await yonetici_girisi(istemci, "yonetici@kulup.com", Rol.admin)
    assert (await getir("yonetici@kulup.com")).sifre_degistirmeli is False
    assert (await istemci.get("/api/auth/me", headers=h)).json()["sifre_degistirmeli"] is False

    y = await istemci.post(
        "/api/antrenorler", headers=h, json={"ad_soyad": "Hoca Bir", "telefon": "0532 000 00 01"}
    )
    assert y.status_code == 201, y.text
    assert (await getir("+905320000001")).sifre_degistirmeli is True
    async with SessionLocal() as s:
        k = await getir("+905320000001")
        k.sifre_degistirmeli = False
        await s.merge(k)
        await s.commit()
    aid = y.json()["antrenor"]["id"]
    assert (await istemci.post(f"/api/antrenorler/{aid}/sifre-sifirla", headers=h)).status_code == 200
    assert (await getir("+905320000001")).sifre_degistirmeli is True


async def test_veli_hesabi_ve_sifirlama_bayrak_koyar(istemci):
    h = await yonetici_girisi(istemci, "yonetici@kulup.com", Rol.admin)
    o = await ogrenci_ac(istemci, h)
    oid = o["id"] if isinstance(o, dict) else o
    y = await istemci.post(f"/api/ogrenciler/{oid}/hesap", headers=h, json={"rol": "veli"})
    assert y.status_code == 200, y.text
    giris = y.json()["giris"]
    assert (await getir(giris)).sifre_degistirmeli is True
    # Veli giriş yapar; /me bayrağı gösterir.
    vh = await login(istemci, giris, y.json()["gecici_sifre"])
    assert (await istemci.get("/api/auth/me", headers=vh)).json()["sifre_degistirmeli"] is True
    async with SessionLocal() as s:
        k = await s.get(Kullanici, (await getir(giris)).id)
        k.sifre_degistirmeli = False
        await s.commit()
    r = await istemci.post(f"/api/ogrenciler/{oid}/hesap/sifre-sifirla", headers=h)
    assert r.status_code == 200
    assert (await getir(giris)).sifre_degistirmeli is True
