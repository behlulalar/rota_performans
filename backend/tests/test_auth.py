import re
from datetime import date, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Antrenor, DenetimKaydi, IletisimKisisi, Kullanici, Ogrenci, Oturum, Rol
from app.models.ogrenci import IletisimRolu
from app.security import simdi
from tests.conftest import SIFRE, kullanici_olustur

GENEL_HATA = "Giriş bilgileri hatalı veya hesap geçici olarak kilitli."


async def giris_yap(istemci, giris="yonetici@kulup.com", sifre=SIFRE, hatirla=None):
    govde = {"giris": giris, "sifre": sifre}
    if hatirla is not None:
        govde["beni_hatirla"] = hatirla
    return await istemci.post("/api/auth/login", json=govde)


def _max_age(yanit) -> int | None:
    eslesme = re.search(r"max-age=(\d+)", yanit.headers["set-cookie"].lower())
    return int(eslesme.group(1)) if eslesme else None


async def _tek_oturum() -> Oturum:
    async with SessionLocal() as session:
        return (await session.execute(select(Oturum).order_by(Oturum.olusturma.desc()))).scalars().first()


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


async def test_beni_hatirla_acik_kalici_cerez_ve_30_gunluk_oturum(istemci):
    await kullanici_olustur()
    yanit = await giris_yap(istemci, hatirla=True)
    assert yanit.status_code == 200
    assert _max_age(yanit) == 30 * 86400
    oturum = await _tek_oturum()
    assert oturum.hatirla is True
    fark = oturum.bitis - simdi()
    assert timedelta(days=29, hours=23) < fark <= timedelta(days=30)


async def test_beni_hatirla_kapali_oturum_cerezi_ve_12_saatlik_oturum(istemci):
    await kullanici_olustur()
    for hatirla in (None, False):
        yanit = await giris_yap(istemci, hatirla=hatirla)
        assert yanit.status_code == 200
        ayar = yanit.headers["set-cookie"].lower()
        assert "max-age" not in ayar
        assert "expires" not in ayar
        assert "httponly" in ayar and "samesite=strict" in ayar and "path=/api/auth" in ayar
        oturum = await _tek_oturum()
        assert oturum.hatirla is False
        fark = oturum.bitis - simdi()
        assert timedelta(hours=11, minutes=55) < fark <= timedelta(hours=12)


async def test_yenileme_hatirla_modunu_ve_cerez_turunu_korur(istemci):
    await kullanici_olustur()
    await giris_yap(istemci, hatirla=True)
    yanit = await istemci.post("/api/auth/refresh")
    assert yanit.status_code == 200
    assert _max_age(yanit) == 30 * 86400
    oturum = await _tek_oturum()
    assert oturum.hatirla is True
    assert oturum.bitis - simdi() > timedelta(days=29, hours=23)

    istemci.cookies.clear()
    await giris_yap(istemci, hatirla=False)
    yanit = await istemci.post("/api/auth/refresh")
    assert yanit.status_code == 200
    ayar = yanit.headers["set-cookie"].lower()
    assert "max-age" not in ayar and "expires" not in ayar
    oturum = await _tek_oturum()
    assert oturum.hatirla is False
    assert timedelta(hours=11, minutes=55) < oturum.bitis - simdi() <= timedelta(hours=12)


async def test_12_saati_gecmis_hatirlamasiz_oturum_yenilenemez(istemci):
    await kullanici_olustur()
    await giris_yap(istemci, hatirla=False)
    async with SessionLocal() as session:
        oturum = (await session.execute(select(Oturum))).scalar_one()
        oturum.bitis = simdi() - timedelta(minutes=1)
        await session.commit()
    assert (await istemci.post("/api/auth/refresh")).status_code == 401


async def test_me_ad_soyad_yonetici_antrenor_veli(istemci):
    async def me(giris):
        belirtec = (await giris_yap(istemci, giris=giris)).json()["access_token"]
        yanit = await istemci.get("/api/auth/me", headers={"Authorization": f"Bearer {belirtec}"})
        assert yanit.status_code == 200
        return yanit.json()["ad_soyad"]

    # Yönetici: kullanıcının kendi adı; yoksa null.
    yonetici = await kullanici_olustur()
    assert await me("yonetici@kulup.com") is None
    async with SessionLocal() as session:
        (await session.get(Kullanici, yonetici.id)).ad_soyad = "Ayşe Yönetici"
        await session.commit()
    assert await me("yonetici@kulup.com") == "Ayşe Yönetici"

    # Antrenör: kullanıcıda ad yoksa antrenör kaydından.
    antrenor = await kullanici_olustur("antrenor@kulup.com", Rol.antrenor)
    async with SessionLocal() as session:
        session.add(Antrenor(kullanici_id=antrenor.id, ad_soyad="Mehmet Antrenör"))
        await session.commit()
    assert await me("antrenor@kulup.com") == "Mehmet Antrenör"

    # Veli: birincil iletişim kişisinin adı.
    veli = await kullanici_olustur("veli@kulup.com", Rol.veli)
    async with SessionLocal() as session:
        ogrenci = Ogrenci(ad="Can", soyad="Yılmaz", dogum_tarihi=date(2015, 5, 10))
        session.add(ogrenci)
        await session.flush()
        session.add_all(
            [
                IletisimKisisi(ogrenci_id=ogrenci.id, rol=IletisimRolu.baba, ad_soyad="Baba Yılmaz", telefon="05550000001"),
                IletisimKisisi(
                    ogrenci_id=ogrenci.id,
                    rol=IletisimRolu.anne,
                    ad_soyad="Fatma Yılmaz",
                    telefon="05550000002",
                    birincil=True,
                    kullanici_id=veli.id,
                ),
            ]
        )
        await session.commit()
    assert await me("veli@kulup.com") == "Fatma Yılmaz"
