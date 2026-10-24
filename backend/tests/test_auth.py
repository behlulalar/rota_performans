from sqlalchemy import select

from app.db import SessionLocal
from app.models import DenetimKaydi, Kullanici, Oturum, Rol
from tests.conftest import SIFRE, kullanici_olustur

GENEL_HATA = "Giriş bilgileri hatalı veya hesap geçici olarak kilitli."


async def giris_yap(istemci, giris="yonetici@kulup.com", sifre=SIFRE):
    return await istemci.post("/api/auth/login", json={"giris": giris, "sifre": sifre})


async def test_saglik(istemci):
    yanit = await istemci.get("/api/saglik")
    assert yanit.status_code == 200
    assert yanit.json() == {"durum": "ok"}


async def test_basarili_giris_ve_me(istemci):
    await kullanici_olustur()
    yanit = await giris_yap(istemci)
    assert yanit.status_code == 200
    belirtec = yanit.json()["access_token"]
    assert "rota_yenileme" in yanit.cookies

    ben = await istemci.get("/api/auth/me", headers={"Authorization": f"Bearer {belirtec}"})
    assert ben.status_code == 200
    assert ben.json()["rol"] == "admin"


async def test_giris_buyuk_kucuk_harf_ve_bosluk_duyarsiz(istemci):
    await kullanici_olustur()
    assert (await giris_yap(istemci, giris="  Yonetici@Kulup.COM ")).status_code == 200


async def test_hatali_sifre_ve_bilinmeyen_hesap_ayni_yaniti_verir(istemci):
    await kullanici_olustur()
    hatali = await giris_yap(istemci, sifre="yanlis")
    bilinmeyen = await giris_yap(istemci, giris="yok@kulup.com")
    assert hatali.status_code == bilinmeyen.status_code == 401
    assert hatali.json() == bilinmeyen.json() == {"detail": GENEL_HATA}


async def test_parola_ve_belirtec_yanita_veya_kayda_sizmaz(istemci):
    await kullanici_olustur()
    await giris_yap(istemci, sifre="yanlis-sifre-xyz")
    async with SessionLocal() as session:
        kayitlar = (await session.execute(select(DenetimKaydi))).scalars().all()
    assert kayitlar
    assert all("yanlis-sifre-xyz" not in str(k.detay) for k in kayitlar)


async def test_bes_hatali_denemeden_sonra_hesap_kilitlenir(istemci):
    await kullanici_olustur()
    for _ in range(5):
        assert (await giris_yap(istemci, sifre="yanlis")).status_code == 401
    # Doğru şifre bile kilitliyken reddedilir.
    yanit = await giris_yap(istemci)
    assert yanit.status_code == 401
    assert yanit.json() == {"detail": GENEL_HATA}


async def test_pasif_hesap_giremez(istemci):
    await kullanici_olustur(aktif=False)
    assert (await giris_yap(istemci)).status_code == 401


async def test_ip_basina_hiz_siniri(istemci):
    for _ in range(20):
        await giris_yap(istemci, giris="yok@kulup.com")
    assert (await giris_yap(istemci, giris="yok@kulup.com")).status_code == 429


async def test_me_belirtec_olmadan_401(istemci):
    assert (await istemci.get("/api/auth/me")).status_code == 401


async def test_me_gecersiz_belirtec_401(istemci):
    yanit = await istemci.get("/api/auth/me", headers={"Authorization": "Bearer sahte.belirtec.degeri"})
    assert yanit.status_code == 401


async def test_pasife_alinan_kullanicinin_belirteci_calismaz(istemci):
    k = await kullanici_olustur()
    belirtec = (await giris_yap(istemci)).json()["access_token"]
    async with SessionLocal() as session:
        kayit = await session.get(Kullanici, k.id)
        kayit.aktif = False
        await session.commit()
    yanit = await istemci.get("/api/auth/me", headers={"Authorization": f"Bearer {belirtec}"})
    assert yanit.status_code == 401


async def test_yenileme_belirteci_doner_ve_eskisi_gecersiz_olur(istemci):
    await kullanici_olustur()
    await giris_yap(istemci)
    eski_cerez = istemci.cookies.get("rota_yenileme")

    yanit = await istemci.post("/api/auth/refresh")
    assert yanit.status_code == 200
    assert istemci.cookies.get("rota_yenileme") != eski_cerez

    # Eski belirteç yeniden kullanılırsa reddedilir ve tüm oturumlar kapanır.
    istemci.cookies.set("rota_yenileme", eski_cerez, path="/api/auth")
    tekrar = await istemci.post("/api/auth/refresh")
    assert tekrar.status_code == 401
    async with SessionLocal() as session:
        oturumlar = (await session.execute(select(Oturum))).scalars().all()
    assert oturumlar and all(o.iptal for o in oturumlar)


async def test_cikis_yenilemeyi_iptal_eder(istemci):
    await kullanici_olustur()
    await giris_yap(istemci)
    cerez = istemci.cookies.get("rota_yenileme")
    assert (await istemci.post("/api/auth/logout")).status_code == 204

    istemci.cookies.set("rota_yenileme", cerez, path="/api/auth")
    assert (await istemci.post("/api/auth/refresh")).status_code == 401


async def test_cerez_ozellikleri(istemci):
    await kullanici_olustur()
    yanit = await giris_yap(istemci)
    ayar = yanit.headers["set-cookie"].lower()
    assert "httponly" in ayar
    assert "secure" in ayar
    assert "samesite=strict" in ayar
    assert "path=/api/auth" in ayar


async def test_belirteclerin_ozeti_saklanir_kendisi_degil(istemci):
    await kullanici_olustur()
    await giris_yap(istemci)
    cerez = istemci.cookies.get("rota_yenileme")
    async with SessionLocal() as session:
        oturum = (await session.execute(select(Oturum))).scalar_one()
    assert oturum.token_ozeti != cerez
    assert len(oturum.token_ozeti) == 64


async def test_guvenlik_basliklari(istemci):
    yanit = await istemci.get("/api/saglik")
    assert yanit.headers["x-content-type-options"] == "nosniff"
    assert yanit.headers["x-frame-options"] == "DENY"
    assert yanit.headers["cache-control"] == "no-store"
