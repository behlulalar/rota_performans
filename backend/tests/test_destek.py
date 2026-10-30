"""Teknik destek hesabı: yetki, yönetici korumaları, panel ayrımı, zorunlu 2FA (TOTP + kurtarma kodu),
sistem durumu, hesap yönetimi ve bildirim kuyruğu uçları."""
import time
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
from redis.asyncio import Redis
from sqlalchemy import select

from app import cli
from app.api.auth import COOKIE_ADI
from app.config import settings
from app.db import SessionLocal
from app.isci import KALP_ATISI_ANAHTAR
from app.models import Bildirim, BildirimDurum, BildirimKanal, DenetimKaydi, Kullanici, Oturum, Rol
from app.security import erisim_belirteci_uret
from tests.conftest import SIFRE, destek_baslik, destek_olustur, kullanici_olustur
from tests.test_bildirim import ortam
from tests.test_bildirim_yonetimi import ekle as bildirim_ekle

D = "/api/destek"
LOGIN = "/api/auth/login"
IKILI = "/api/auth/2fa"


async def login(istemci, giris, panel=None, sifre=SIFRE):
    govde = {"giris": giris, "sifre": sifre}
    if panel:
        govde["panel"] = panel
    return await istemci.post(LOGIN, json=govde)


async def baslik(istemci, giris, rol, panel):
    await kullanici_olustur(giris, rol)
    y = await login(istemci, giris, panel)
    assert y.status_code == 200, y.text
    return {"Authorization": f"Bearer {y.json()['access_token']}"}


async def kayit(giris):
    async with SessionLocal() as s:
        return (await s.execute(select(Kullanici).where(Kullanici.giris == giris))).scalar_one()


async def kodu_serbest_birak():
    """Aynı zaman adımındaki kod tekrar kullanılamaz; testte art arda doğrulama için işaretleri siler."""
    r = Redis.from_url(settings.redis_url)
    async for a in r.scan_iter("2fa:kullanilan:*"):
        await r.delete(a)
    await r.aclose()


async def denetim(islem):
    async with SessionLocal() as s:
        return (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == islem))).scalars().all()


# --- Yetki ---


async def test_destek_yonetici_uclarina_erisir(istemci):
    h = await destek_baslik(istemci)
    for yol in ("/api/yoneticiler", "/api/antrenorler", "/api/bildirim-yonetimi/ozet", "/api/ogrenciler"):
        assert (await istemci.get(yol, headers=h)).status_code == 200, yol
    # Antrenör/veli panel uçları rol bazlı kalır.
    assert (await istemci.get("/api/veli/ben", headers=h)).status_code in (403, 404)


async def test_admin_ve_digerleri_destek_uclarina_giremez(istemci):
    admin = await baslik(istemci, "admin@kulup.com", Rol.admin, "yonetici")
    hoca = await baslik(istemci, "hoca@kulup.com", Rol.antrenor, "antrenor")
    yollar = [
        "/api/denetim", "/api/denetim/islemler", f"{D}/sistem-durumu", f"{D}/hesaplar", f"{D}/bildirimler",
    ]
    for yol in yollar:
        assert (await istemci.get(yol)).status_code == 401, yol
        assert (await istemci.get(yol, headers=admin)).status_code == 403, yol
        assert (await istemci.get(yol, headers=hoca)).status_code == 403, yol
    assert (await istemci.post(f"{D}/bildirimler/toplu-iptal", json={"tum_hatalilar": True}, headers=admin)).status_code == 403


# --- Yönetici ekranı korumaları ---


async def test_admin_destek_hesabini_duzenleyemez(istemci):
    admin = await baslik(istemci, "admin@kulup.com", Rol.admin, "yonetici")
    destek, _ = await destek_olustur()
    liste = (await istemci.get("/api/yoneticiler", headers=admin)).json()
    d = next(x for x in liste if x["giris"] == "destek@kulup.com")
    assert d["destek"] is True and all(x["destek"] is False for x in liste if x["giris"] != "destek@kulup.com")
    url = f"/api/yoneticiler/{destek.id}"
    assert (await istemci.patch(url, json={"ad_soyad": "X"}, headers=admin)).status_code == 403
    assert (await istemci.patch(url, json={"aktif": False}, headers=admin)).status_code == 403
    assert (await istemci.post(f"{url}/sifre-sifirla", headers=admin)).status_code == 403
    k = await kayit("destek@kulup.com")
    assert k.aktif and k.ad_soyad == "Destek"


async def test_yoneticiler_sayfasindan_destek_olusturulamaz(istemci):
    admin = await baslik(istemci, "admin@kulup.com", Rol.admin, "yonetici")
    y = await istemci.post("/api/yoneticiler", json={"ad_soyad": "Yeni", "giris": "yeni@kulup.com", "rol": "destek"}, headers=admin)
    assert y.status_code == 201
    assert (await kayit("yeni@kulup.com")).rol == Rol.admin


async def test_destek_son_yonetici_sayimina_girmez(istemci):
    admin = await baslik(istemci, "admin@kulup.com", Rol.admin, "yonetici")
    _, gizli = await destek_olustur()
    yonetici_id = (await kayit("admin@kulup.com")).id
    # Aktif bir destek hesabı olsa da tek aktif admin pasife alınamaz.
    y = await istemci.patch(f"/api/yoneticiler/{yonetici_id}", json={"aktif": False}, headers=admin)
    assert y.status_code == 409
    h = await destek_baslik(istemci, gizli=gizli)
    y = await istemci.post(f"{D}/hesaplar/{yonetici_id}/pasif", headers=h)
    assert y.status_code == 409
    assert (await kayit("admin@kulup.com")).aktif


async def test_destek_baska_destegi_pasife_alabilir_kendini_alamaz(istemci):
    h = await destek_baslik(istemci)
    ikinci, _ = await destek_olustur("destek2@kulup.com")
    ben = (await kayit("destek@kulup.com")).id
    assert (await istemci.post(f"{D}/hesaplar/{ben}/pasif", headers=h)).status_code == 422
    y = await istemci.post(f"{D}/hesaplar/{ikinci.id}/pasif", headers=h)  # admin yok: destek sayıma girmez, engellenmez
    assert y.status_code == 200 and y.json()["aktif"] is False
    assert (await istemci.post(f"{D}/hesaplar/{ikinci.id}/aktif", headers=h)).json()["aktif"] is True


# --- Panel ayrımı ---


async def test_panel_ayrimi(istemci):
    await destek_olustur()
    await kullanici_olustur("admin@kulup.com", Rol.admin)
    # Destek yönetici panelinden ve panelsiz genel girişten giremez.
    assert (await login(istemci, "destek@kulup.com", "yonetici")).status_code == 401
    assert (await login(istemci, "destek@kulup.com")).status_code == 401
    assert (await login(istemci, "destek@kulup.com", "veli")).status_code == 401
    # Admin destek panelinden giremez.
    assert (await login(istemci, "admin@kulup.com", "destek")).status_code == 401
    assert (await login(istemci, "admin@kulup.com", "yonetici")).status_code == 200
    # Destek kendi panelinden girer ama oturum yerine 2. adım alır.
    y = await login(istemci, "destek@kulup.com", "destek")
    assert y.status_code == 200
    d = y.json()
    assert d["iki_adim"] is True and d["durum"] == "dogrulama" and "access_token" not in d
    assert COOKIE_ADI not in y.cookies


# --- 2FA ---


async def test_ikili_kurulum_ve_dogrulama(istemci):
    await destek_olustur(totp=False)
    y = (await login(istemci, "destek@kulup.com", "destek")).json()
    assert y["durum"] == "kurulum"
    bek = y["bekleyen_belirtec"]

    k = await istemci.post(f"{IKILI}/kurulum", json={"bekleyen_belirtec": bek})
    assert k.status_code == 200
    gizli = k.json()["gizli_anahtar"]
    uri = k.json()["otpauth_uri"]
    assert uri.startswith("otpauth://totp/") and gizli in uri and "Rota" in uri
    # Gizli anahtar veritabanında düz saklanmaz; kurulum doğrulanana kadar etkin değildir.
    dbk = await kayit("destek@kulup.com")
    assert dbk.totp_aktif is False and gizli.encode() not in dbk.totp_sifreli

    kotu = await istemci.post(f"{IKILI}/kurulum-dogrula", json={"bekleyen_belirtec": bek, "kod": "000000"})
    assert kotu.status_code == 401
    iyi = await istemci.post(f"{IKILI}/kurulum-dogrula", json={"bekleyen_belirtec": bek, "kod": pyotp.TOTP(gizli).now()})
    assert iyi.status_code == 200, iyi.text
    d = iyi.json()
    assert len(d["kurtarma_kodlari"]) == 8 and len(set(d["kurtarma_kodlari"])) == 8
    assert COOKIE_ADI in iyi.cookies
    h = {"Authorization": f"Bearer {d['access_token']}"}
    assert (await istemci.get(f"{D}/sistem-durumu", headers=h)).status_code == 200
    dbk = await kayit("destek@kulup.com")
    assert dbk.totp_aktif is True and len(dbk.totp_kurtarma) == 8
    assert all(kod not in str(dbk.totp_kurtarma) for kod in d["kurtarma_kodlari"])  # yalnız özet
    # Bekleyen belirteç kullanıldı.
    assert (await istemci.post(f"{IKILI}/kurulum", json={"bekleyen_belirtec": bek})).status_code == 401

    # Sonraki girişte kurulum kapalı, doğrulama istenir; aynı adımdaki kod tekrar kullanılamaz.
    y = (await login(istemci, "destek@kulup.com", "destek")).json()
    assert y["durum"] == "dogrulama"
    assert (await istemci.post(f"{IKILI}/kurulum", json={"bekleyen_belirtec": y["bekleyen_belirtec"]})).status_code == 409
    assert (await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": y["bekleyen_belirtec"], "kod": pyotp.TOTP(gizli).now()})).status_code == 401
    # ±1 pencere: bir önceki adımın kodu kabul edilir, iki adım öncesi edilmez.
    onceki = pyotp.TOTP(gizli).at(time.time() - 30)
    cok_eski = pyotp.TOTP(gizli).at(time.time() - 90)
    assert (await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": y["bekleyen_belirtec"], "kod": cok_eski})).status_code == 401
    ok = await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": y["bekleyen_belirtec"], "kod": onceki})
    assert ok.status_code == 200 and "access_token" in ok.json()
    assert (await kayit("destek@kulup.com")).son_giris is not None
    assert (await denetim("ikili_kurulum_tamamlandi")) and (await denetim("ikili_dogrulama_basarisiz"))


async def test_yanlis_kod_kilit_mantigina_sayilir(istemci):
    _, gizli = await destek_olustur()
    bek = (await login(istemci, "destek@kulup.com", "destek")).json()["bekleyen_belirtec"]
    for i in range(4):
        y = await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": bek, "kod": "123456"})
        assert y.status_code == 401
    assert (await kayit("destek@kulup.com")).basarisiz_deneme == 4
    y = await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": bek, "kod": "123456"})
    assert y.status_code == 401
    k = await kayit("destek@kulup.com")
    assert k.kilit_bitis is not None and k.kilit_bitis > datetime.now(timezone.utc)
    # Kilitliyken doğru kodla ve doğru şifreyle de girilemez; bekleyen belirteç de silindi.
    y = await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": bek, "kod": pyotp.TOTP(gizli).now()})
    assert y.status_code == 401
    assert (await login(istemci, "destek@kulup.com", "destek")).status_code == 401


async def test_sifre_adimi_sayaci_sifirlamaz(istemci):
    """Şifre doğru girilince sayaç sıfırlanmamalı, yoksa kod denemeleri yeniden giriş yapılarak sınırsız olurdu."""
    await destek_olustur()
    for _ in range(2):
        bek = (await login(istemci, "destek@kulup.com", "destek")).json()["bekleyen_belirtec"]
        await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": bek, "kod": "123456"})
    assert (await kayit("destek@kulup.com")).basarisiz_deneme == 2


async def test_kurtarma_kodu_tek_kullanimlik(istemci):
    await destek_olustur(totp=False)
    bek = (await login(istemci, "destek@kulup.com", "destek")).json()["bekleyen_belirtec"]
    gizli = (await istemci.post(f"{IKILI}/kurulum", json={"bekleyen_belirtec": bek})).json()["gizli_anahtar"]
    kodlar = (
        await istemci.post(f"{IKILI}/kurulum-dogrula", json={"bekleyen_belirtec": bek, "kod": pyotp.TOTP(gizli).now()})
    ).json()["kurtarma_kodlari"]

    bek = (await login(istemci, "destek@kulup.com", "destek")).json()["bekleyen_belirtec"]
    y = await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": bek, "kod": kodlar[0].upper()})  # büyük harf de olur
    assert y.status_code == 200
    assert len((await kayit("destek@kulup.com")).totp_kurtarma) == 7
    # Aynı kod ikinci kez geçmez, kullanılmamış olan geçer.
    bek = (await login(istemci, "destek@kulup.com", "destek")).json()["bekleyen_belirtec"]
    assert (await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": bek, "kod": kodlar[0]})).status_code == 401
    assert (await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": bek, "kod": kodlar[1]})).status_code == 200
    assert (await denetim("ikili_kurtarma_kodu_kullanildi"))


async def test_ikili_tamamlanmadan_korumali_uclar_kapali(istemci):
    k, _ = await destek_olustur(totp=False)
    y = await login(istemci, "destek@kulup.com", "destek")
    assert "access_token" not in y.json() and COOKIE_ADI not in y.cookies
    bek = y.json()["bekleyen_belirtec"]
    # Bekleyen belirteç erişim belirteci yerine geçmez.
    assert (await istemci.get(f"{D}/sistem-durumu", headers={"Authorization": f"Bearer {bek}"})).status_code == 401
    assert (await istemci.get("/api/auth/me", headers={"Authorization": f"Bearer {bek}"})).status_code == 401
    assert (await istemci.post("/api/auth/refresh")).status_code == 401
    # 2FA'sı olmayan destek hesabı için üretilmiş bir erişim belirteci bile işe yaramaz.
    sahte = {"Authorization": f"Bearer {erisim_belirteci_uret(k.id, Rol.destek)}"}
    for yol in (f"{D}/sistem-durumu", "/api/denetim", "/api/yoneticiler", "/api/auth/me"):
        y = await istemci.get(yol, headers=sahte)
        assert y.status_code == 403 and y.headers["X-Hata-Kodu"] == "ikili_dogrulama", yol
    # Geçersiz/uydurma bekleyen belirteç.
    assert (await istemci.post(f"{IKILI}/dogrula", json={"bekleyen_belirtec": "x" * 40, "kod": "123456"})).status_code == 401
    # Çok kısa belirteç şema doğrulamasına takılır.
    assert (await istemci.post(f"{IKILI}/kurulum", json={"bekleyen_belirtec": "kisa"})).status_code == 422


async def test_cli_2fa_sifirlama(istemci):
    h = await destek_baslik(istemci)
    assert (await istemci.get(f"{D}/sistem-durumu", headers=h)).status_code == 200
    assert await cli.destek_2fa_sifirla("DESTEK@kulup.com") == 0
    k = await kayit("destek@kulup.com")
    assert k.totp_aktif is False and k.totp_sifreli is None and k.totp_kurtarma is None
    # Eski oturum ve belirteç kapandı; yeniden girişte kurulum istenir.
    assert (await istemci.get(f"{D}/sistem-durumu", headers=h)).status_code == 403
    assert (await login(istemci, "destek@kulup.com", "destek")).json()["durum"] == "kurulum"
    await kullanici_olustur("admin@kulup.com", Rol.admin)
    assert await cli.destek_2fa_sifirla("admin@kulup.com") == 1  # destek olmayan hesap


# --- Sistem durumu ---


async def test_sistem_durumu(istemci):
    h = await destek_baslik(istemci)
    d = (await istemci.get(f"{D}/sistem-durumu", headers=h)).json()
    assert d["ortam"] == "test" and d["surum"] == settings.surum == "geliştirme"
    assert d["veritabani"]["ok"] and d["veritabani"]["gecikme_ms"] >= 0
    assert d["redis"]["ok"] and d["redis"]["gecikme_ms"] >= 0
    assert d["isci"] == {"canli": False, "son_atis": None, "saniye_once": None}
    assert d["bildirim_kuyrugu"] == {"bekliyor": 0, "gonderildi": 0, "hata": 0, "iptal": 0, "geciken_bekleyen": 0}
    assert d["push_yapilandirildi"] is settings.push_etkin
    assert d["whatsapp_yapilandirildi"] is False

    r = Redis.from_url(settings.redis_url)
    await r.set(KALP_ATISI_ANAHTAR, str(int(time.time()) - 5))
    d = (await istemci.get(f"{D}/sistem-durumu", headers=h)).json()
    assert d["isci"]["canli"] is True and 4 <= d["isci"]["saniye_once"] < 30 and d["isci"]["son_atis"]
    await r.set(KALP_ATISI_ANAHTAR, str(int(time.time()) - 600))
    assert (await istemci.get(f"{D}/sistem-durumu", headers=h)).json()["isci"]["canli"] is False
    await r.aclose()

    o, _, kisi = await ortam()
    await bildirim_ekle(o, kisi, durum=BildirimDurum.hata, hata="x")
    await bildirim_ekle(o, kisi, planli=datetime.now(timezone.utc) - timedelta(minutes=5))
    q = (await istemci.get(f"{D}/sistem-durumu", headers=h)).json()["bildirim_kuyrugu"]
    assert q["hata"] == 1 and q["bekliyor"] == 1 and q["geciken_bekleyen"] == 1


# --- Hesap yönetimi ---


async def test_hesap_listesi_ve_filtre(istemci):
    h = await destek_baslik(istemci)
    await kullanici_olustur("admin@kulup.com", Rol.admin)
    await kullanici_olustur("hoca@kulup.com", Rol.antrenor)
    await kullanici_olustur("veli1@kulup.com", Rol.veli)
    d = (await istemci.get(f"{D}/hesaplar", headers=h)).json()
    assert d["toplam"] == 4 and {x["rol"] for x in d["kayitlar"]} == {"destek", "admin", "antrenor", "veli"}
    assert [x["ben"] for x in d["kayitlar"] if x["giris"] == "destek@kulup.com"] == [True]
    assert all({"id", "giris", "ad_soyad", "rol", "aktif", "kilitli", "kilit_bitis", "son_giris"} <= set(x) for x in d["kayitlar"])
    assert (await istemci.get(f"{D}/hesaplar?rol=veli", headers=h)).json()["toplam"] == 1
    assert (await istemci.get(f"{D}/hesaplar?q=HOCA", headers=h)).json()["kayitlar"][0]["giris"] == "hoca@kulup.com"
    assert (await istemci.get(f"{D}/hesaplar?q=%25", headers=h)).json()["toplam"] == 0
    s = (await istemci.get(f"{D}/hesaplar?boyut=2&sayfa=2", headers=h)).json()
    assert s["toplam"] == 4 and len(s["kayitlar"]) == 2
    assert (await istemci.get(f"{D}/hesaplar?rol=yok", headers=h)).status_code == 422


async def test_kilit_ac_ve_sifre_sifirla(istemci):
    h = await destek_baslik(istemci)
    hoca = await kullanici_olustur("hoca@kulup.com", Rol.antrenor)
    for _ in range(5):
        await login(istemci, "hoca@kulup.com", sifre="yanlis-sifre")
    assert (await login(istemci, "hoca@kulup.com")).status_code == 401  # kilitli
    satir = next(x for x in (await istemci.get(f"{D}/hesaplar?rol=antrenor", headers=h)).json()["kayitlar"])
    assert satir["kilitli"] is True and satir["kilit_bitis"]
    y = await istemci.post(f"{D}/hesaplar/{hoca.id}/kilit-ac", headers=h)
    assert y.status_code == 200 and y.json()["kilitli"] is False
    assert (await login(istemci, "hoca@kulup.com")).status_code == 200

    y = await istemci.post(f"{D}/hesaplar/{hoca.id}/sifre-sifirla", headers=h)
    assert y.status_code == 200
    gecici = y.json()["gecici_sifre"]
    k = await kayit("hoca@kulup.com")
    assert k.sifre_degistirmeli is True
    assert (await login(istemci, "hoca@kulup.com")).status_code == 401  # eski şifre geçmez
    assert (await login(istemci, "hoca@kulup.com", sifre=gecici)).status_code == 200
    # Kendi şifresini bu uçtan sıfırlayamaz; olmayan hesap 404.
    ben = (await kayit("destek@kulup.com")).id
    assert (await istemci.post(f"{D}/hesaplar/{ben}/sifre-sifirla", headers=h)).status_code == 422
    assert (await istemci.post(f"{D}/hesaplar/{uuid.UUID(int=0)}/kilit-ac", headers=h)).status_code == 404


async def test_pasif_aktif_ve_oturumlar(istemci):
    h = await destek_baslik(istemci)
    hoca = await kullanici_olustur("hoca@kulup.com", Rol.antrenor)
    for _ in range(2):
        assert (await login(istemci, "hoca@kulup.com")).status_code == 200
    o = (await istemci.get(f"{D}/hesaplar/{hoca.id}/oturumlar", headers=h)).json()
    assert len(o) == 2 and all(x["aktif"] for x in o) and "token_ozeti" not in str(o)

    y = await istemci.post(f"{D}/hesaplar/{hoca.id}/oturumlari-kapat", headers=h)
    assert y.json() == {"kapatilan": 2}
    assert not any(x["aktif"] for x in (await istemci.get(f"{D}/hesaplar/{hoca.id}/oturumlar", headers=h)).json())
    assert (await istemci.post(f"{D}/hesaplar/{hoca.id}/oturumlari-kapat", headers=h)).json() == {"kapatilan": 0}

    assert (await login(istemci, "hoca@kulup.com")).status_code == 200
    y = await istemci.post(f"{D}/hesaplar/{hoca.id}/pasif", headers=h)
    assert y.status_code == 200 and y.json()["aktif"] is False
    assert (await login(istemci, "hoca@kulup.com")).status_code == 401
    async with SessionLocal() as s:
        assert not (await s.execute(select(Oturum).where(Oturum.kullanici_id == hoca.id, Oturum.iptal.is_(False)))).scalars().all()
    assert (await istemci.post(f"{D}/hesaplar/{hoca.id}/aktif", headers=h)).json()["aktif"] is True
    assert (await login(istemci, "hoca@kulup.com")).status_code == 200


async def test_destek_islemleri_denetime_yazilir(istemci):
    h = await destek_baslik(istemci)
    hoca = await kullanici_olustur("hoca@kulup.com", Rol.antrenor)
    await istemci.post(f"{D}/hesaplar/{hoca.id}/kilit-ac", headers=h)
    await istemci.post(f"{D}/hesaplar/{hoca.id}/sifre-sifirla", headers=h)
    await istemci.post(f"{D}/hesaplar/{hoca.id}/pasif", headers=h)
    await istemci.post(f"{D}/hesaplar/{hoca.id}/aktif", headers=h)
    await istemci.post(f"{D}/hesaplar/{hoca.id}/oturumlari-kapat", headers=h)
    r = (await istemci.get("/api/denetim?ara=destek", headers=h)).json()
    islemler = {x["islem"] for x in r["items"]}
    assert {"destek_kilit_acildi", "destek_sifre_sifirlandi", "destek_hesap_pasife_alindi",
            "destek_hesap_aktife_alindi", "destek_oturumlar_kapatildi"} <= islemler
    kayit_ = next(x for x in r["items"] if x["islem"] == "destek_kilit_acildi")
    assert kayit_["kullanici"]["rol"] == "destek" and kayit_["hedef_id"] == str(hoca.id)
    assert "gecici" not in str(r)


# --- Bildirim kuyruğu ---


async def test_bildirimler_teknik_gorunum(istemci):
    h = await destek_baslik(istemci)
    o, _, kisi = await ortam()
    hata_id = await bildirim_ekle(o, kisi, durum=BildirimDurum.hata, hata="push servisi 500", deneme=5)
    await bildirim_ekle(o, kisi, kanal=BildirimKanal.whatsapp)
    d = (await istemci.get(f"{D}/bildirimler", headers=h)).json()
    assert d["toplam"] == 2
    s = next(x for x in d["kayitlar"] if x["id"] == hata_id)
    assert s["hata"] == "push servisi 500" and s["deneme"] == 5 and s["parametreler"]["bakiye"] == 2
    assert s["ogrenci_id"] == str(o) and s["alici_iletisim_id"] == str(kisi) and s["metin"]
    assert (await istemci.get(f"{D}/bildirimler?durum=hata", headers=h)).json()["toplam"] == 1
    assert (await istemci.get(f"{D}/bildirimler?kanal=whatsapp", headers=h)).json()["toplam"] == 1
    assert (await istemci.get(f"{D}/bildirimler?boyut=1&sayfa=2", headers=h)).json()["kayitlar"].__len__() == 1


async def test_toplu_yeniden_dene_ve_iptal(istemci):
    h = await destek_baslik(istemci)
    o, _, kisi = await ortam()
    h1 = await bildirim_ekle(o, kisi, durum=BildirimDurum.hata, hata="a", deneme=5)
    h2 = await bildirim_ekle(o, kisi, durum=BildirimDurum.hata, hata="b", deneme=5)
    g = await bildirim_ekle(o, kisi, durum=BildirimDurum.gonderildi)
    b = await bildirim_ekle(o, kisi)

    async def durum(i):
        async with SessionLocal() as s:
            return (await s.get(Bildirim, i)).durum

    # Doğrulama: ikisi birden ya da hiçbiri olmaz.
    assert (await istemci.post(f"{D}/bildirimler/toplu-iptal", json={}, headers=h)).status_code == 422
    assert (await istemci.post(f"{D}/bildirimler/toplu-iptal", json={"ids": [h1], "tum_hatalilar": True}, headers=h)).status_code == 422

    y = await istemci.post(f"{D}/bildirimler/toplu-yeniden-dene", json={"ids": [h1, g, 99999]}, headers=h)
    assert y.json() == {"islenen": 1, "atlanan": 2}
    assert await durum(h1) == BildirimDurum.bekliyor and await durum(g) == BildirimDurum.gonderildi
    async with SessionLocal() as s:
        assert (await s.get(Bildirim, h1)).deneme == 0

    y = await istemci.post(f"{D}/bildirimler/toplu-yeniden-dene", json={"tum_hatalilar": True}, headers=h)
    assert y.json() == {"islenen": 1, "atlanan": 0} and await durum(h2) == BildirimDurum.bekliyor

    y = await istemci.post(f"{D}/bildirimler/toplu-iptal", json={"ids": [h1, g, b]}, headers=h)
    assert y.json() == {"islenen": 2, "atlanan": 1}
    assert await durum(h1) == await durum(b) == BildirimDurum.iptal and await durum(g) == BildirimDurum.gonderildi

    async with SessionLocal() as s:
        (await s.get(Bildirim, h2)).durum = BildirimDurum.hata
        await s.commit()
    y = await istemci.post(f"{D}/bildirimler/toplu-iptal", json={"tum_hatalilar": True}, headers=h)
    assert y.json() == {"islenen": 1, "atlanan": 0} and await durum(h2) == BildirimDurum.iptal
    assert (await denetim("destek_bildirim_toplu_yeniden_denendi")) and (await denetim("destek_bildirim_toplu_iptal"))


async def test_e2e_tohumu_destek_hesabi(istemci, monkeypatch):
    monkeypatch.setenv("E2E_ADMIN_GIRIS", "yonetici@e2e.test")
    monkeypatch.setenv("E2E_ADMIN_SIFRE", "Yonetici-test-sifre-1")
    assert await cli.e2e_tohum() == 0
    assert await cli.e2e_tohum() == 0  # tekrar çalışınca bozulmaz
    k = await kayit("destek@rota.test")
    assert k.rol == Rol.destek and k.totp_aktif is False and k.totp_sifreli is None
    y = await login(istemci, "destek@rota.test", "destek", sifre=cli.E2E_DESTEK_SIFRE)
    assert y.json()["durum"] == "kurulum"


async def test_destek_telefonla_girer_ve_telefonunu_degistirir(istemci):
    h = await destek_baslik(istemci)
    r = await istemci.patch("/api/auth/telefon", json={"telefon": "05321112233", "sifre": SIFRE}, headers=h)
    assert r.status_code == 200, r.text
    r = await login(istemci, "0532 111 22 33", panel="destek")
    assert r.status_code == 200 and r.json()["iki_adim"] is True
    # Telefon yönetici panelinden destek hesabına giriş açmaz.
    assert (await login(istemci, "05321112233", panel="yonetici")).status_code == 401
