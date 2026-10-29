"""Yöneticinin e-posta YA DA telefonla girişi (kullanici.telefon)."""
import json

import pytest
from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import DenetimKaydi, Kullanici, Oturum, Rol
from tests.conftest import SIFRE, kullanici_olustur
from tests.test_ogrenciler import giris as yonetici_girisi
from tests.test_veli_hesaplari import hesap_ac, ogrenci_ac
from tests.test_yoneticiler import URL, aktif_oturum_sayisi, kayit, login

TEL = "+905321112233"
TEL2 = "+905329998877"


@pytest.fixture
async def yonetici(istemci):
    return await yonetici_girisi(istemci, "yonetici@kulup.com", Rol.admin)


def h(b):
    return {k: v for k, v in b.items() if not k.startswith("_")}


async def yonetici_ac(istemci, b, giris="ayse@kulup.com", telefon=TEL, ad="Ayşe Yılmaz"):
    return await istemci.post(URL, json={"ad_soyad": ad, "giris": giris, "telefon": telefon}, headers=h(b))


async def telefon_yaz(giris_, telefon):
    async with SessionLocal() as s:
        await s.execute(update(Kullanici).where(Kullanici.giris == giris_).values(telefon=telefon))
        await s.commit()


async def telefonla_giris(istemci, giris_, sifre=SIFRE, **ek):
    return await istemci.post("/api/auth/login", json={"giris": giris_, "sifre": sifre, **ek})


async def test_telefonla_giris_ayni_hesap_farkli_bicimler(istemci, yonetici):
    y = await yonetici_ac(istemci, yonetici, telefon="0532 111 22 33")
    assert y.status_code == 201, y.text
    assert y.json()["yonetici"]["telefon"] == TEL
    k = await kayit("ayse@kulup.com")
    # Geçici şifre ile (SIFRE değil) giriş: şifreyi doğrudan ayarla
    from app.security import sifre_ozeti

    async with SessionLocal() as s:
        await s.execute(update(Kullanici).where(Kullanici.id == k.id).values(sifre_ozeti=sifre_ozeti(SIFRE)))
        await s.commit()
    for bicim in ["0532 111 22 33", "+905321112233", "5321112233", "0(532) 111-22-33"]:
        r = await telefonla_giris(istemci, bicim, panel="yonetici")
        assert r.status_code == 200, (bicim, r.text)
        b = {"Authorization": f"Bearer {r.json()['access_token']}"}
        me = (await istemci.get("/api/auth/me", headers=b)).json()
        assert me["id"] == str(k.id) and me["giris"] == "ayse@kulup.com" and me["telefon"] == TEL
    # e-posta ile de girer
    assert (await telefonla_giris(istemci, "ayse@kulup.com")).status_code == 200
    # Yanlış panel reddedilir
    assert (await telefonla_giris(istemci, TEL, panel="veli")).status_code == 401


async def test_antrenor_ve_veli_telefon_alani_giris_yolu_degil(istemci):
    hoca = await kullanici_olustur("hoca@kulup.com", Rol.antrenor)
    veli = await kullanici_olustur("+905554443322", Rol.veli)
    await telefon_yaz("hoca@kulup.com", TEL)
    await telefon_yaz("+905554443322", TEL2)
    assert (await telefonla_giris(istemci, TEL)).status_code == 401
    assert (await telefonla_giris(istemci, TEL2)).status_code == 401
    # Kendi girişleri çalışır
    assert (await telefonla_giris(istemci, "hoca@kulup.com")).status_code == 200
    assert (await telefonla_giris(istemci, "0555 444 33 22")).status_code == 200
    assert hoca.id != veli.id


async def test_kilit_sayaci_ortak(istemci):
    await kullanici_olustur("yonetici@kulup.com", Rol.admin)
    await telefon_yaz("yonetici@kulup.com", TEL)
    for g in ["yonetici@kulup.com", TEL, "0532 111 22 33", "yonetici@kulup.com", TEL]:
        assert (await telefonla_giris(istemci, g, "yanlis-sifre-1")).status_code == 401
    k = await kayit("yonetici@kulup.com")
    assert k.kilit_bitis is not None
    # Kilitliyken doğru şifre iki yoldan da reddedilir
    assert (await telefonla_giris(istemci, TEL)).status_code == 401
    assert (await telefonla_giris(istemci, "yonetici@kulup.com")).status_code == 401
    async with SessionLocal() as s:
        n = len((await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "giris_basarisiz"))).scalars().all())
    assert n >= 5


async def test_olustur_ve_guncelle_telefon(istemci, yonetici):
    y = await yonetici_ac(istemci, yonetici, telefon=None)
    assert y.status_code == 201 and y.json()["yonetici"]["telefon"] is None
    yid = y.json()["yonetici"]["id"]
    p = await istemci.patch(f"{URL}/{yid}", json={"telefon": "0532 111 22 33"}, headers=h(yonetici))
    assert p.status_code == 200 and p.json()["telefon"] == TEL
    assert (await kayit("ayse@kulup.com")).telefon == TEL
    liste = (await istemci.get(URL, headers=h(yonetici))).json()
    assert [x["telefon"] for x in liste if x["id"] == yid] == [TEL]
    # geçersiz
    assert (await istemci.patch(f"{URL}/{yid}", json={"telefon": "123"}, headers=h(yonetici))).status_code == 422
    # kaldır
    p = await istemci.patch(f"{URL}/{yid}", json={"telefon": ""}, headers=h(yonetici))
    assert p.status_code == 200 and p.json()["telefon"] is None
    # giriş zaten telefonsa aynı telefon verilirse telefon boş kalır
    y2 = await yonetici_ac(istemci, yonetici, giris="0533 000 11 22", telefon="+905330001122", ad="Veli Can")
    assert y2.status_code == 201 and y2.json()["yonetici"]["telefon"] is None
    assert y2.json()["yonetici"]["giris"] == "+905330001122"
    # kendi telefonu bu uçtan değişmez
    ben = [x for x in liste if x["ben"]][0]
    assert (await istemci.patch(f"{URL}/{ben['id']}", json={"telefon": TEL2}, headers=h(yonetici))).status_code == 422


async def test_yonetici_telefon_cakismalari(istemci, yonetici):
    veli = await kullanici_olustur("+905554443322", Rol.veli)
    assert veli
    # başka kullanıcının girişi
    r = await yonetici_ac(istemci, yonetici, telefon="0555 444 33 22")
    assert r.status_code == 409 and "telefon/giriş" in r.json()["detail"]
    assert (await yonetici_ac(istemci, yonetici)).status_code == 201
    # başka yöneticinin telefonu
    r = await yonetici_ac(istemci, yonetici, giris="b@kulup.com", telefon=TEL)
    assert r.status_code == 409
    # telefon olarak başka yöneticinin telefonu girişe yazılamaz
    r = await istemci.post(URL, json={"ad_soyad": "X Y", "giris": TEL}, headers=h(yonetici))
    assert r.status_code == 409 and "telefon/giriş" in r.json()["detail"]
    r2 = await yonetici_ac(istemci, yonetici, giris="c@kulup.com", telefon=None)
    cid = r2.json()["yonetici"]["id"]
    assert (await istemci.patch(f"{URL}/{cid}", json={"giris": TEL}, headers=h(yonetici))).status_code == 409
    assert (await istemci.patch(f"{URL}/{cid}", json={"telefon": TEL}, headers=h(yonetici))).status_code == 409
    assert (await istemci.patch(f"{URL}/{cid}", json={"telefon": "+905554443322"}, headers=h(yonetici))).status_code == 409
    # kendi telefonunu aynen göndermek çakışma değil
    aid = (await istemci.get(URL, headers=h(yonetici))).json()
    ayse = [x for x in aid if x["giris"] == "ayse@kulup.com"][0]
    assert (await istemci.patch(f"{URL}/{ayse['id']}", json={"telefon": TEL}, headers=h(yonetici))).status_code == 200


async def test_antrenor_ve_veli_hesabi_yonetici_telefonuyla_cakisamaz(istemci, yonetici):
    assert (await yonetici_ac(istemci, yonetici)).status_code == 201
    r = await istemci.post("/api/antrenorler", json={"ad_soyad": "Hoca Bir", "giris": "0532 111 22 33"}, headers=h(yonetici))
    assert r.status_code == 409 and "telefon/giriş" in r.json()["detail"]
    ok = await istemci.post("/api/antrenorler", json={"ad_soyad": "Hoca Bir", "giris": "hoca@kulup.com"}, headers=h(yonetici))
    assert ok.status_code == 201, ok.text
    aid = ok.json()["antrenor"]["id"]
    p = await istemci.patch(f"/api/antrenorler/{aid}", json={"giris": TEL}, headers=h(yonetici))
    assert p.status_code == 409
    # Antrenör kartındaki iletişim telefonu (Antrenor.telefon) giriş değildir: çakışma aranmaz
    p = await istemci.patch(f"/api/antrenorler/{aid}", json={"telefon": TEL}, headers=h(yonetici))
    assert p.status_code == 200
    # Veli hesabı
    o = await ogrenci_ac(istemci, yonetici, telefon="0532 111 22 33")
    r = await hesap_ac(istemci, yonetici, o["id"])
    assert r.status_code == 409 and "telefon/giriş" in r.json()["detail"]
    r = await hesap_ac(istemci, yonetici, o["id"], giris="veli@kulup.com")
    assert r.status_code == 200, r.text


TEL_URL = "/api/auth/telefon"


async def test_kendi_telefonunu_degistirme(istemci):
    h1 = await login(istemci, (await kullanici_olustur("yonetici@kulup.com", Rol.admin)).giris)
    k = await kayit("yonetici@kulup.com")
    h2 = await login(istemci, "yonetici@kulup.com")
    assert await aktif_oturum_sayisi(k.id) == 2
    # yanlış şifre
    r = await istemci.patch(TEL_URL, json={"telefon": "0532 111 22 33", "sifre": "yanlis"}, headers=h2)
    assert r.status_code == 400
    assert (await kayit("yonetici@kulup.com")).telefon is None
    # geçersiz / e-posta
    assert (await istemci.patch(TEL_URL, json={"telefon": "123", "sifre": SIFRE}, headers=h2)).status_code == 422
    assert (await istemci.patch(TEL_URL, json={"telefon": "a@b.com", "sifre": SIFRE}, headers=h2)).status_code == 422
    # başarı
    r = await istemci.patch(TEL_URL, json={"telefon": "0532 111 22 33", "sifre": SIFRE}, headers=h2)
    assert r.status_code == 200 and r.json()["telefon"] == TEL
    assert await aktif_oturum_sayisi(k.id) == 1
    assert (await telefonla_giris(istemci, "532 111 22 33")).status_code == 200
    h3 = await login(istemci, TEL)
    # aynı değer
    assert (await istemci.patch(TEL_URL, json={"telefon": TEL, "sifre": SIFRE}, headers=h3)).status_code == 422
    # kaldır
    r = await istemci.patch(TEL_URL, json={"telefon": "", "sifre": SIFRE}, headers=h3)
    assert r.status_code == 200 and r.json()["telefon"] is None
    assert (await telefonla_giris(istemci, TEL)).status_code == 401
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem.like("telefon_deg%")))).scalars().all()
    assert {x.islem for x in kayitlar} == {"telefon_degisti", "telefon_degistirme_basarisiz"}
    metin = json.dumps([[x.detay, x.hedef_id] for x in kayitlar])
    assert "5321112233" not in metin and SIFRE not in metin and "yanlis" not in metin
    assert h1


async def test_kendi_telefonu_cakisma_ve_yetki(istemci):
    await kullanici_olustur("yonetici@kulup.com", Rol.admin)
    b = await login(istemci, "yonetici@kulup.com")
    await kullanici_olustur("+905554443322", Rol.veli)
    await kullanici_olustur("baska@kulup.com", Rol.admin)
    await telefon_yaz("baska@kulup.com", TEL)
    for t in ["0555 444 33 22", TEL]:
        r = await istemci.patch(TEL_URL, json={"telefon": t, "sifre": SIFRE}, headers=b)
        assert r.status_code == 409 and "telefon/giriş" in r.json()["detail"]
    # kendi girişini başkasının telefonuna çeviremez
    r = await istemci.patch("/api/auth/giris", json={"yeni_giris": TEL, "sifre": SIFRE}, headers=b)
    assert r.status_code == 409 and "telefon/giriş" in r.json()["detail"]
    # antrenör kullanamaz
    await kullanici_olustur("hoca@kulup.com", Rol.antrenor)
    hb = await login(istemci, "hoca@kulup.com")
    assert (await istemci.patch(TEL_URL, json={"telefon": TEL2, "sifre": SIFRE}, headers=hb)).status_code == 403
    assert (await istemci.patch(TEL_URL, json={"telefon": TEL2, "sifre": SIFRE})).status_code == 401


async def test_giris_telefona_cevrilince_telefon_alani_temizlenir(istemci):
    await kullanici_olustur("yonetici@kulup.com", Rol.admin)
    await telefon_yaz("yonetici@kulup.com", TEL)
    b = await login(istemci, "yonetici@kulup.com")
    r = await istemci.patch("/api/auth/giris", json={"yeni_giris": TEL, "sifre": SIFRE}, headers=b)
    assert r.status_code == 200, r.text
    assert r.json()["giris"] == TEL and r.json()["telefon"] is None


async def test_telefon_tekil_indeks(istemci):
    await kullanici_olustur("a@kulup.com", Rol.admin)
    await kullanici_olustur("b@kulup.com", Rol.admin)
    await telefon_yaz("a@kulup.com", TEL)
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await telefon_yaz("b@kulup.com", TEL)
    assert Oturum
