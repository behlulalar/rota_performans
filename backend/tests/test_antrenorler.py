import json

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DenetimKaydi, Kullanici, Oturum, Rol
from tests.conftest import SIFRE, kullanici_olustur


async def giris(istemci, eposta, rol):
    await kullanici_olustur(eposta, rol)
    yanit = await istemci.post("/api/auth/login", json={"giris": eposta, "sifre": SIFRE})
    return {"Authorization": f"Bearer {yanit.json()['access_token']}"}


@pytest.fixture
async def yonetici(istemci):
    return await giris(istemci, "yonetici@kulup.com", Rol.admin)


async def olustur(istemci, baslik, **ek):
    govde = {"ad_soyad": "Ali Hoca", "telefon": "0532 000 00 00", "giris": "ali@kulup.com"}
    govde.update(ek)
    return await istemci.post("/api/antrenorler", json=govde, headers=baslik)


async def test_olusturma_ve_gecici_sifreyle_giris(istemci, yonetici):
    yanit = await olustur(istemci, yonetici)
    assert yanit.status_code == 201, yanit.text
    d = yanit.json()
    sifre = d["gecici_sifre"]
    assert len(sifre) >= 12
    assert any(c.isalpha() for c in sifre) and any(c.isdigit() for c in sifre)
    assert not set(sifre) & set("0OlI1")
    assert d["antrenor"]["giris"] == "ali@kulup.com"
    assert d["antrenor"]["aktif"] is True
    assert d["antrenor"]["grup_sayisi"] == 0
    assert d["antrenor"]["telefon"] == "+905320000000"

    giris_yaniti = await istemci.post("/api/auth/login", json={"giris": "ALI@kulup.com", "sifre": sifre})
    assert giris_yaniti.status_code == 200
    ben = await istemci.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {giris_yaniti.json()['access_token']}"}
    )
    assert ben.json()["rol"] == "antrenor"

    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi))).scalars().all()
    assert any(k.islem == "antrenor_olusturuldu" for k in kayitlar)
    assert sifre not in json.dumps([[k.islem, k.detay, k.hedef_id] for k in kayitlar])


async def test_telefonla_giris_olusturma(istemci, yonetici):
    yanit = await olustur(istemci, yonetici, giris="+90 532 111 22 33")
    assert yanit.status_code == 201
    assert yanit.json()["antrenor"]["giris"] == "+905321112233"


async def test_tekrar_giris_409(istemci, yonetici):
    assert (await olustur(istemci, yonetici)).status_code == 201
    yanit = await olustur(istemci, yonetici, ad_soyad="Başka", giris="ALI@kulup.com")
    assert yanit.status_code == 409
    assert yanit.json()["detail"] == "Bu giriş bilgisi başka bir hesapta kayıtlı"


@pytest.mark.parametrize("gecersiz", ["abc", "a@b", "123", "ali@", "12345abc"])
async def test_gecersiz_giris_422(istemci, yonetici, gecersiz):
    assert (await olustur(istemci, yonetici, giris=gecersiz)).status_code == 422


async def test_liste_ve_filtre_ve_sira(istemci, yonetici):
    await olustur(istemci, yonetici, ad_soyad="Zeynep", giris="z@kulup.com")
    b = (await olustur(istemci, yonetici, ad_soyad="Ayşe", giris="a@kulup.com")).json()["antrenor"]
    await istemci.patch(f"/api/antrenorler/{b['id']}", json={"aktif": False}, headers=yonetici)
    tum = (await istemci.get("/api/antrenorler", headers=yonetici)).json()
    assert [a["ad_soyad"] for a in tum] == ["Ayşe", "Zeynep"]
    aktifler = (await istemci.get("/api/antrenorler?aktif=true", headers=yonetici)).json()
    assert [a["ad_soyad"] for a in aktifler] == ["Zeynep"]
    pasifler = (await istemci.get("/api/antrenorler?aktif=false", headers=yonetici)).json()
    assert [a["ad_soyad"] for a in pasifler] == ["Ayşe"]


async def test_pasife_alma_girisi_ve_yenilemeyi_keser(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    sifre = d["gecici_sifre"]
    giris_yaniti = await istemci.post("/api/auth/login", json={"giris": "ali@kulup.com", "sifre": sifre})
    assert giris_yaniti.status_code == 200
    erisim = {"Authorization": f"Bearer {giris_yaniti.json()['access_token']}"}

    yanit = await istemci.patch(f"/api/antrenorler/{d['antrenor']['id']}", json={"aktif": False}, headers=yonetici)
    assert yanit.status_code == 200
    assert yanit.json()["aktif"] is False

    assert (await istemci.post("/api/auth/refresh")).status_code == 401
    assert (await istemci.get("/api/auth/me", headers=erisim)).status_code == 401
    assert (
        await istemci.post("/api/auth/login", json={"giris": "ali@kulup.com", "sifre": sifre})
    ).status_code == 401
    async with SessionLocal() as s:
        oturumlar = (
            await s.execute(
                select(Oturum).join(Kullanici, Kullanici.id == Oturum.kullanici_id).where(Kullanici.rol == Rol.antrenor)
            )
        ).scalars().all()
        assert oturumlar and all(o.iptal for o in oturumlar)

    # Tekrar aktif edilince giriş yeniden mümkün.
    await istemci.patch(f"/api/antrenorler/{d['antrenor']['id']}", json={"aktif": True}, headers=yonetici)
    assert (
        await istemci.post("/api/auth/login", json={"giris": "ali@kulup.com", "sifre": sifre})
    ).status_code == 200


async def test_guncelle_ad_ve_telefon(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()["antrenor"]
    yanit = await istemci.patch(
        f"/api/antrenorler/{d['id']}", json={"ad_soyad": "  Veli Hoca ", "telefon": None}, headers=yonetici
    )
    assert yanit.status_code == 200
    assert yanit.json()["ad_soyad"] == "Veli Hoca"
    assert yanit.json()["telefon"] is None
    assert (
        await istemci.patch(f"/api/antrenorler/{d['id']}", json={"ad_soyad": "  "}, headers=yonetici)
    ).status_code == 422


async def test_sifre_sifirlama(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    eski = d["gecici_sifre"]
    assert (await istemci.post("/api/auth/login", json={"giris": "ali@kulup.com", "sifre": eski})).status_code == 200
    yanit = await istemci.post(f"/api/antrenorler/{d['antrenor']['id']}/sifre-sifirla", headers=yonetici)
    assert yanit.status_code == 200
    yeni = yanit.json()["gecici_sifre"]
    assert yeni != eski and len(yeni) >= 12
    # Mevcut oturum belirteci artık çalışmaz.
    assert (await istemci.post("/api/auth/refresh")).status_code == 401
    assert (await istemci.post("/api/auth/login", json={"giris": "ali@kulup.com", "sifre": eski})).status_code == 401
    assert (await istemci.post("/api/auth/login", json={"giris": "ali@kulup.com", "sifre": yeni})).status_code == 200
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi))).scalars().all()
    assert any(k.islem == "antrenor_sifre_sifirlandi" for k in kayitlar)
    assert yeni not in json.dumps([[k.islem, k.detay] for k in kayitlar])


async def test_sifre_sifirlama_kilidi_acar(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    for _ in range(5):
        await istemci.post("/api/auth/login", json={"giris": "ali@kulup.com", "sifre": "yanlis-sifre"})
    async with SessionLocal() as s:
        k = (await s.execute(select(Kullanici).where(Kullanici.giris == "ali@kulup.com"))).scalar_one()
        assert k.kilit_bitis is not None
    yeni = (await istemci.post(f"/api/antrenorler/{d['antrenor']['id']}/sifre-sifirla", headers=yonetici)).json()
    assert (
        await istemci.post("/api/auth/login", json={"giris": "ali@kulup.com", "sifre": yeni["gecici_sifre"]})
    ).status_code == 200


async def test_bulunamadi_404(istemci, yonetici):
    sahte = "00000000-0000-0000-0000-000000000000"
    for yanit in (
        await istemci.patch(f"/api/antrenorler/{sahte}", json={"aktif": False}, headers=yonetici),
        await istemci.post(f"/api/antrenorler/{sahte}/sifre-sifirla", headers=yonetici),
    ):
        assert yanit.status_code == 404
        assert yanit.json()["detail"] == "Antrenör bulunamadı"


async def test_yetki(istemci, yonetici):
    antrenor = await giris(istemci, "hoca@kulup.com", Rol.antrenor)
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    sahte = "00000000-0000-0000-0000-000000000000"
    uclar = [
        ("get", "/api/antrenorler", None),
        ("post", "/api/antrenorler", {"ad_soyad": "X", "giris": "x@kulup.com"}),
        ("patch", f"/api/antrenorler/{sahte}", {"aktif": False}),
        ("post", f"/api/antrenorler/{sahte}/sifre-sifirla", None),
    ]
    for yontem, yol, govde in uclar:
        for baslik in (antrenor, veli):
            assert (await istemci.request(yontem, yol, json=govde, headers=baslik)).status_code == 403
        assert (await istemci.request(yontem, yol, json=govde)).status_code == 401


async def test_antrenor_farkli_yazimla_giris(istemci, yonetici):
    y = await olustur(istemci, yonetici, giris="0532 111 22 33")
    assert y.status_code == 201, y.text
    assert y.json()["antrenor"]["giris"] == "+905321112233"
    sifre = y.json()["gecici_sifre"]
    for g in ("+905321112233", "5321112233", "0 532 111 22 33", "90 532 111 22 33"):
        r = await istemci.post("/api/auth/login", json={"giris": g, "sifre": sifre})
        assert r.status_code == 200, g


async def test_antrenor_gecersiz_telefon_422(istemci, yonetici):
    for t in ("abc", "532123456", "053212345678"):
        assert (await olustur(istemci, yonetici, telefon=t)).status_code == 422
    assert (await olustur(istemci, yonetici, giris="12345")).status_code == 422
    d = (await olustur(istemci, yonetici)).json()["antrenor"]
    y = await istemci.patch(f"/api/antrenorler/{d['id']}", json={"telefon": "123"}, headers=yonetici)
    assert y.status_code == 422


async def test_giris_degistirme_oturumlari_kapatir(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    aid = d["antrenor"]["id"]
    await istemci.post("/api/auth/login", json={"giris": "ali@kulup.com", "sifre": d["gecici_sifre"]})
    async with SessionLocal() as s:
        k = (await s.execute(select(Kullanici).where(Kullanici.giris == "ali@kulup.com"))).scalar_one()
        assert len((await s.execute(select(Oturum).where(Oturum.kullanici_id == k.id, Oturum.iptal.is_(False)))).scalars().all()) == 1

    y = await istemci.patch(f"/api/antrenorler/{aid}", json={"giris": " ALI.Yeni@kulup.com"}, headers=yonetici)
    assert y.status_code == 200, y.text
    assert y.json()["giris"] == "ali.yeni@kulup.com"
    async with SessionLocal() as s:
        assert (await s.execute(select(Oturum).where(Oturum.kullanici_id == k.id, Oturum.iptal.is_(False)))).first() is None
        kayitlar = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "antrenor_guncellendi"))).scalars().all()
    assert "ali.yeni@kulup.com" not in json.dumps([x.detay for x in kayitlar])
    assert (await istemci.post("/api/auth/login", json={"giris": "ali@kulup.com", "sifre": d["gecici_sifre"]})).status_code == 401
    assert (await istemci.post("/api/auth/login", json={"giris": "ali.yeni@kulup.com", "sifre": d["gecici_sifre"]})).status_code == 200

    # Telefon normalizasyonu
    y = await istemci.patch(f"/api/antrenorler/{aid}", json={"giris": "0532 999 88 77"}, headers=yonetici)
    assert y.status_code == 200 and y.json()["giris"] == "+905329998877"


async def test_giris_degistirme_409_ve_422(istemci, yonetici):
    await kullanici_olustur("veli@kulup.com", Rol.veli)
    aid = (await olustur(istemci, yonetici)).json()["antrenor"]["id"]
    for g in ["veli@kulup.com", "yonetici@kulup.com"]:
        assert (await istemci.patch(f"/api/antrenorler/{aid}", json={"giris": g}, headers=yonetici)).status_code == 409
    for g in ["abc", None]:
        assert (await istemci.patch(f"/api/antrenorler/{aid}", json={"giris": g}, headers=yonetici)).status_code == 422
    # Aynı giriş: sorun yok, oturum da kapanmaz
    assert (await istemci.patch(f"/api/antrenorler/{aid}", json={"giris": "ali@kulup.com"}, headers=yonetici)).status_code == 200
