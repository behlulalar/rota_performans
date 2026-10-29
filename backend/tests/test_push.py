"""Web Push: gönderim (pywebpush çağrısı taklit edilir), yeniden deneme, abonelik API'si."""
import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app import push
from app.config import settings
from app.db import SessionLocal
from app.models import Bildirim, BildirimDurum, BildirimKanal, DenetimKaydi, PushAbonelik, Rol, YoklamaDurum
from tests.conftest import kullanici_olustur
from tests.test_bildirim import T0, isaretle, oturum, ortam
from tests.test_veli_paneli import baslik, veli_ve_cocuk
from tests.test_yoklama import yonetici  # noqa: F401  (fixture)

ENDPOINT = "https://push.ornek.test/abc"
ANAHTAR = {"p256dh": "p" * 20, "auth": "a" * 10}


@pytest.fixture
def etkin(monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "PUB")
    monkeypatch.setattr(settings, "vapid_private_key", "PRIV")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:a@b.com")


@pytest.fixture
def gonderilenler(monkeypatch):
    """Taklit gönderici: dönüş kodu sabit verilir, çağrılar kaydedilir."""
    k = {"kod": 0, "cagrilar": []}

    def sahte(bilgi, veri):
        k["cagrilar"].append((bilgi, veri))
        return k["kod"]

    monkeypatch.setattr(push, "_gonder_senkron", sahte)
    return k


async def kur(abonelik=True):
    """Gelmedi işaretli öğrenci + hesaplı veli; push bildirimi (T0+3dk planlı) hazır."""
    ogr, kul, _ = await ortam()
    if abonelik:
        async with SessionLocal() as s:
            s.add(PushAbonelik(kullanici_id=kul, endpoint=ENDPOINT, **ANAHTAR))
            await s.commit()
    await isaretle(ogr, await oturum(), YoklamaDurum.gelmedi)
    return ogr, kul


async def calistir(simdi):
    async with SessionLocal() as s:
        sonuc = await push.push_gonder(s, simdi)
        await s.commit()
    return sonuc


async def push_bildirimi():
    async with SessionLocal() as s:
        return (await s.execute(select(Bildirim).where(Bildirim.kanal == BildirimKanal.push))).scalar_one()


async def abonelik_sayisi():
    async with SessionLocal() as s:
        return len(list((await s.execute(select(PushAbonelik))).scalars()))


async def test_basarili_gonderim(etkin, gonderilenler):
    ogr, _ = await kur()
    assert (await calistir(T0))["gonderildi"] == 0  # geri alma süresi dolmadı
    sonuc = await calistir(T0 + timedelta(minutes=5))
    assert sonuc["gonderildi"] == 1
    b = await push_bildirimi()
    assert b.durum == BildirimDurum.gonderildi and b.gonderim_zamani is not None
    bilgi, veri = gonderilenler["cagrilar"][0]
    assert bilgi["endpoint"] == ENDPOINT and bilgi["keys"]["auth"] == ANAHTAR["auth"]
    yuk = json.loads(veri)
    assert yuk["baslik"] == "Rota Performans" and yuk["url"] == f"/panel/cocuk/{ogr}"
    assert "Deniz" in yuk["govde"]
    # Tekrar çalışınca yeniden gönderilmez.
    await calistir(T0 + timedelta(minutes=6))
    assert len(gonderilenler["cagrilar"]) == 1


async def test_410_aboneligi_siler(etkin, gonderilenler):
    await kur()
    gonderilenler["kod"] = 410
    sonuc = await calistir(T0 + timedelta(minutes=5))
    assert sonuc["silinen_abonelik"] == 1
    assert await abonelik_sayisi() == 0
    b = await push_bildirimi()
    assert b.durum == BildirimDurum.hata and b.hata == "abonelik yok"


async def test_genel_hata_geri_cekilmeyle_yeniden_denenir(etkin, gonderilenler):
    await kur()
    gonderilenler["kod"] = 500
    an = T0 + timedelta(minutes=5)
    for deneme in range(1, push.MAKS_DENEME):
        await calistir(an)
        b = await push_bildirimi()
        assert b.durum == BildirimDurum.bekliyor and b.deneme == deneme
        assert b.planli_zaman == an + timedelta(minutes=2**deneme)
        # Bekleme dolmadan tekrar denenmez.
        n = len(gonderilenler["cagrilar"])
        await calistir(an + timedelta(minutes=2**deneme - 1))
        assert len(gonderilenler["cagrilar"]) == n
        an = b.planli_zaman
    await calistir(an)
    b = await push_bildirimi()
    assert b.durum == BildirimDurum.hata and b.deneme == push.MAKS_DENEME
    assert b.hata == "push servisi hatası"
    assert await abonelik_sayisi() == 1  # geçici hatada abonelik silinmez


async def test_hata_sonrasi_basari(etkin, gonderilenler):
    await kur()
    gonderilenler["kod"] = -1
    an = T0 + timedelta(minutes=5)
    await calistir(an)
    gonderilenler["kod"] = 0
    await calistir(an + timedelta(minutes=2))
    assert (await push_bildirimi()).durum == BildirimDurum.gonderildi


async def test_abonelik_yoksa_hata(etkin, gonderilenler):
    await kur(abonelik=False)
    await calistir(T0 + timedelta(minutes=5))
    b = await push_bildirimi()
    assert b.durum == BildirimDurum.hata and b.hata == "abonelik yok"
    assert gonderilenler["cagrilar"] == []


async def test_ayar_yoksa_gonderilmez(monkeypatch, gonderilenler):
    monkeypatch.setattr(settings, "vapid_private_key", "")
    await kur()
    sonuc = await calistir(T0 + timedelta(minutes=5))
    assert not any(sonuc.values()) and gonderilenler["cagrilar"] == []
    assert (await push_bildirimi()).durum == BildirimDurum.bekliyor


async def test_eski_bildirim_iptal(etkin, gonderilenler):
    await kur()
    sonuc = await calistir(T0 + timedelta(hours=25))
    assert sonuc["iptal"] == 1 and gonderilenler["cagrilar"] == []
    b = await push_bildirimi()
    assert b.durum == BildirimDurum.iptal and b.hata == "süresi geçti"


async def test_birden_cok_abonelikten_biri_yeter(etkin, gonderilenler):
    _, kul = await kur()
    async with SessionLocal() as s:
        s.add(PushAbonelik(kullanici_id=kul, endpoint=ENDPOINT + "2", **ANAHTAR))
        await s.commit()
    await calistir(T0 + timedelta(minutes=5))
    assert len(gonderilenler["cagrilar"]) == 2
    assert (await push_bildirimi()).durum == BildirimDurum.gonderildi


# ---------- API ----------


async def test_api_yetki(istemci, yonetici):  # noqa: F811
    await kullanici_olustur("antrenor@kulup.com", Rol.antrenor)
    for u, m in [("/api/benim/push/anahtar", "GET"), ("/api/benim/push/abonelik", "POST"), ("/api/benim/push/abonelik", "DELETE")]:
        assert (await istemci.request(m, u, json={} if m != "GET" else None)).status_code == 401
    for h in (yonetici, await baslik(istemci, "antrenor@kulup.com")):
        assert (await istemci.get("/api/benim/push/anahtar", headers=h)).status_code == 403
        assert (
            await istemci.post("/api/benim/push/abonelik", headers=h, json={"endpoint": ENDPOINT, "keys": ANAHTAR})
        ).status_code == 403


async def test_anahtar(istemci, monkeypatch):
    await veli_ve_cocuk()
    h = await baslik(istemci)
    monkeypatch.setattr(settings, "vapid_public_key", "")
    assert (await istemci.get("/api/benim/push/anahtar", headers=h)).json() == {"etkin": False, "anahtar": None}
    monkeypatch.setattr(settings, "vapid_public_key", "PUB")
    monkeypatch.setattr(settings, "vapid_private_key", "PRIV")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:a@b.com")
    assert (await istemci.get("/api/benim/push/anahtar", headers=h)).json() == {"etkin": True, "anahtar": "PUB"}


async def test_abonelik_kaydet_tasi_sil(istemci):
    k1, _ = await veli_ve_cocuk()
    k2, _ = await veli_ve_cocuk(giris="+905559998877", ad="Veli2")
    h1, h2 = await baslik(istemci), await baslik(istemci, "+905559998877")
    govde = {"endpoint": ENDPOINT, "keys": ANAHTAR, "cihaz": "iPhone"}
    assert (await istemci.post("/api/benim/push/abonelik", headers=h1, json=govde)).status_code == 204
    # Aynı uç nokta tekrar: çoğalmaz, anahtarlar güncellenir.
    govde["keys"] = {"p256dh": "yeni" * 5, "auth": "yeni" * 3}
    assert (await istemci.post("/api/benim/push/abonelik", headers=h1, json=govde)).status_code == 204
    async with SessionLocal() as s:
        satirlar = list((await s.execute(select(PushAbonelik))).scalars())
        assert len(satirlar) == 1 and satirlar[0].kullanici_id == k1.id and satirlar[0].p256dh == "yeni" * 5
    # Başka hesap aynı cihazı kaydederse oraya taşınır.
    assert (await istemci.post("/api/benim/push/abonelik", headers=h2, json=govde)).status_code == 204
    async with SessionLocal() as s:
        satirlar = list((await s.execute(select(PushAbonelik))).scalars())
        assert len(satirlar) == 1 and satirlar[0].kullanici_id == k2.id
        islemler = {d.islem for d in (await s.execute(select(DenetimKaydi))).scalars()}
        assert "push_abonelik_kaydedildi" in islemler
    # Eski sahip silemez; yeni sahip siler.
    assert (await istemci.request("DELETE", "/api/benim/push/abonelik", headers=h1, json={"endpoint": ENDPOINT})).status_code == 204
    assert await abonelik_sayisi() == 1
    assert (await istemci.request("DELETE", "/api/benim/push/abonelik", headers=h2, json={"endpoint": ENDPOINT})).status_code == 204
    assert await abonelik_sayisi() == 0


async def test_abonelik_dogrulama(istemci):
    await veli_ve_cocuk()
    h = await baslik(istemci)
    kotu = [
        {"endpoint": "http://push.ornek.test/abc", "keys": ANAHTAR},
        {"endpoint": "https://x.test/" + "a" * 2000, "keys": ANAHTAR},
        {"endpoint": ENDPOINT, "keys": {"p256dh": "", "auth": "a"}},
        {"endpoint": ENDPOINT, "keys": {"p256dh": "x" * 256, "auth": "a"}},
        {"endpoint": ENDPOINT, "keys": ANAHTAR, "cihaz": "c" * 256},
        {"endpoint": ENDPOINT},
    ]
    for g in kotu:
        assert (await istemci.post("/api/benim/push/abonelik", headers=h, json=g)).status_code == 422, g
    assert await abonelik_sayisi() == 0
