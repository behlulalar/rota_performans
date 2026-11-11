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
    govde = {"ad_soyad": "Ali Hoca", "telefon": "0532 000 00 00"}
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
    assert d["antrenor"]["giris"] == "+905320000000"
    assert d["antrenor"]["aktif"] is True
    assert d["antrenor"]["grup_sayisi"] == 0
    assert d["antrenor"]["telefon"] == "+905320000000"

    giris_yaniti = await istemci.post("/api/auth/login", json={"giris": "0532 000 00 00", "sifre": sifre})
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
    yanit = await olustur(istemci, yonetici, telefon="+90 532 111 22 33")
    assert yanit.status_code == 201
    assert yanit.json()["antrenor"]["giris"] == "+905321112233"


async def test_tekrar_giris_409(istemci, yonetici):
    assert (await olustur(istemci, yonetici)).status_code == 201
    yanit = await olustur(istemci, yonetici, ad_soyad="Başka", telefon="532 000 00 00")
    assert yanit.status_code == 409
    assert yanit.json()["detail"] == "Bu giriş bilgisi başka bir hesapta kayıtlı"


@pytest.mark.parametrize("gecersiz", ["abc", "a@b", "123", "ali@kulup.com", "12345abc", ""])
async def test_gecersiz_giris_422(istemci, yonetici, gecersiz):
    assert (await olustur(istemci, yonetici, telefon=gecersiz)).status_code == 422


async def test_liste_ve_filtre_ve_sira(istemci, yonetici):
    await olustur(istemci, yonetici, ad_soyad="Zeynep", telefon="0532 000 00 01")
    b = (await olustur(istemci, yonetici, ad_soyad="Ayşe", telefon="0532 000 00 02")).json()["antrenor"]
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
    giris_yaniti = await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": sifre})
    assert giris_yaniti.status_code == 200
    erisim = {"Authorization": f"Bearer {giris_yaniti.json()['access_token']}"}

    yanit = await istemci.patch(f"/api/antrenorler/{d['antrenor']['id']}", json={"aktif": False}, headers=yonetici)
    assert yanit.status_code == 200
    assert yanit.json()["aktif"] is False

    assert (await istemci.post("/api/auth/refresh")).status_code == 401
    assert (await istemci.get("/api/auth/me", headers=erisim)).status_code == 401
    assert (
        await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": sifre})
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
        await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": sifre})
    ).status_code == 200


async def test_guncelle_ad_ve_telefon(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()["antrenor"]
    yanit = await istemci.patch(
        f"/api/antrenorler/{d['id']}", json={"ad_soyad": "  Veli Hoca ", "telefon": "0533 111 22 33"}, headers=yonetici
    )
    assert yanit.status_code == 200
    assert yanit.json()["ad_soyad"] == "Veli Hoca"
    assert yanit.json()["telefon"] == "+905331112233"
    assert (
        await istemci.patch(f"/api/antrenorler/{d['id']}", json={"ad_soyad": "  "}, headers=yonetici)
    ).status_code == 422
    for bos in (None, "", "  "):
        assert (
            await istemci.patch(f"/api/antrenorler/{d['id']}", json={"telefon": bos}, headers=yonetici)
        ).status_code == 422


async def test_sifre_sifirlama(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    eski = d["gecici_sifre"]
    assert (await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": eski})).status_code == 200
    yanit = await istemci.post(f"/api/antrenorler/{d['antrenor']['id']}/sifre-sifirla", headers=yonetici)
    assert yanit.status_code == 200
    yeni = yanit.json()["gecici_sifre"]
    assert yeni != eski and len(yeni) >= 12
    # Mevcut oturum belirteci artık çalışmaz.
    assert (await istemci.post("/api/auth/refresh")).status_code == 401
    assert (await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": eski})).status_code == 401
    assert (await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": yeni})).status_code == 200
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi))).scalars().all()
    assert any(k.islem == "antrenor_sifre_sifirlandi" for k in kayitlar)
    assert yeni not in json.dumps([[k.islem, k.detay] for k in kayitlar])


async def test_sifre_sifirlama_kilidi_acar(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    for _ in range(5):
        await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": "yanlis-sifre"})
    async with SessionLocal() as s:
        k = (await s.execute(select(Kullanici).where(Kullanici.giris == "+905320000000"))).scalar_one()
        assert k.kilit_bitis is not None
    yeni = (await istemci.post(f"/api/antrenorler/{d['antrenor']['id']}/sifre-sifirla", headers=yonetici)).json()
    assert (
        await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": yeni["gecici_sifre"]})
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
        ("post", "/api/antrenorler", {"ad_soyad": "X", "telefon": "0532 111 22 33"}),
        ("patch", f"/api/antrenorler/{sahte}", {"aktif": False}),
        ("post", f"/api/antrenorler/{sahte}/sifre-sifirla", None),
    ]
    for yontem, yol, govde in uclar:
        for baslik in (antrenor, veli):
            assert (await istemci.request(yontem, yol, json=govde, headers=baslik)).status_code == 403
        assert (await istemci.request(yontem, yol, json=govde)).status_code == 401


async def test_antrenor_farkli_yazimla_giris(istemci, yonetici):
    y = await olustur(istemci, yonetici, telefon="0532 111 22 33")
    assert y.status_code == 201, y.text
    assert y.json()["antrenor"]["giris"] == "+905321112233"
    sifre = y.json()["gecici_sifre"]
    for g in ("+905321112233", "5321112233", "0 532 111 22 33", "90 532 111 22 33"):
        r = await istemci.post("/api/auth/login", json={"giris": g, "sifre": sifre})
        assert r.status_code == 200, g


async def test_antrenor_gecersiz_telefon_422(istemci, yonetici):
    for t in ("abc", "532123456", "053212345678"):
        assert (await olustur(istemci, yonetici, telefon=t)).status_code == 422
    d = (await olustur(istemci, yonetici)).json()["antrenor"]
    y = await istemci.patch(f"/api/antrenorler/{d['id']}", json={"telefon": "123"}, headers=yonetici)
    assert y.status_code == 422


async def test_telefon_degisince_giris_guncellenir_ve_oturumlar_kapanir(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    aid = d["antrenor"]["id"]
    await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": d["gecici_sifre"]})
    async with SessionLocal() as s:
        k = (await s.execute(select(Kullanici).where(Kullanici.giris == "+905320000000"))).scalar_one()
        assert len((await s.execute(select(Oturum).where(Oturum.kullanici_id == k.id, Oturum.iptal.is_(False)))).scalars().all()) == 1

    y = await istemci.patch(f"/api/antrenorler/{aid}", json={"telefon": "0532 999 88 77"}, headers=yonetici)
    assert y.status_code == 200, y.text
    assert y.json()["giris"] == "+905329998877" and y.json()["telefon"] == "+905329998877"
    async with SessionLocal() as s:
        assert (await s.execute(select(Oturum).where(Oturum.kullanici_id == k.id, Oturum.iptal.is_(False)))).first() is None
    assert (await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": d["gecici_sifre"]})).status_code == 401
    assert (await istemci.post("/api/auth/login", json={"giris": "0532 999 88 77", "sifre": d["gecici_sifre"]})).status_code == 200

    # Aynı telefon: sorun yok, oturum kapanmaz
    await istemci.post("/api/auth/login", json={"giris": "+905329998877", "sifre": d["gecici_sifre"]})
    assert (await istemci.patch(f"/api/antrenorler/{aid}", json={"telefon": "+905329998877"}, headers=yonetici)).status_code == 200
    async with SessionLocal() as s:
        assert (await s.execute(select(Oturum).where(Oturum.kullanici_id == k.id, Oturum.iptal.is_(False)))).first() is not None


async def test_telefon_degistirme_409_ve_422(istemci, yonetici):
    await kullanici_olustur("+905321110000", Rol.veli)
    aid = (await olustur(istemci, yonetici)).json()["antrenor"]["id"]
    assert (await istemci.patch(f"/api/antrenorler/{aid}", json={"telefon": "0532 111 00 00"}, headers=yonetici)).status_code == 409
    assert (await istemci.patch(f"/api/antrenorler/{aid}", json={"telefon": "abc"}, headers=yonetici)).status_code == 422
    assert (await istemci.patch(f"/api/antrenorler/{aid}", json={"telefon": "ali@kulup.com"}, headers=yonetici)).status_code == 422
    # giris alanı artık kabul edilmez (yok sayılır)
    y = await istemci.patch(f"/api/antrenorler/{aid}", json={"giris": "x@kulup.com"}, headers=yonetici)
    assert y.status_code == 200 and y.json()["giris"] == "+905320000000"


async def test_eski_antrenor_eposta_girisi_telefonla_degisir(istemci, yonetici):
    """Eski kayıt: giriş e-posta, telefon farklı. Kaydedince ikisi de yeni telefon olur."""
    aid = (await olustur(istemci, yonetici)).json()["antrenor"]["id"]
    async with SessionLocal() as s:
        k = (await s.execute(select(Kullanici).where(Kullanici.giris == "+905320000000"))).scalar_one()
        k.giris = "eski@kulup.com"
        await s.commit()
    y = await istemci.patch(f"/api/antrenorler/{aid}", json={"telefon": "0532 777 66 55"}, headers=yonetici)
    assert y.status_code == 200 and y.json()["giris"] == "+905327776655"


async def test_hesapsiz_antrenorde_yalniz_telefon_guncellenir(istemci, yonetici):
    from app.models.program import Antrenor

    async with SessionLocal() as s:
        a = Antrenor(kullanici_id=None, ad_soyad="Hesapsız", telefon=None, aktif=True)
        s.add(a)
        await s.commit()
        aid = str(a.id)
    y = await istemci.patch(f"/api/antrenorler/{aid}", json={"telefon": "0532 777 66 55"}, headers=yonetici)
    assert y.status_code == 200 and y.json()["telefon"] == "+905327776655" and y.json()["giris"] is None


async def grup_ac(ad, aktif=True, antrenor_id=None):
    from app.models.program import Grup

    async with SessionLocal() as s:
        g = Grup(ad=ad, kontenjan=10, aktif=aktif, antrenor_id=antrenor_id)
        s.add(g)
        await s.commit()
        return str(g.id)


async def grup_sahibi(gid):
    from app.models.program import Grup

    async with SessionLocal() as s:
        a = (await s.execute(select(Grup.antrenor_id).where(Grup.id == gid))).scalar_one()
        return None if a is None else str(a)


async def test_olusturmada_gruplar_atanir(istemci, yonetici):
    g1, g2 = await grup_ac("U10"), await grup_ac("U12")
    y = await olustur(istemci, yonetici, grup_idleri=[g1, g2])
    assert y.status_code == 201, y.text
    a = y.json()["antrenor"]
    assert a["grup_sayisi"] == 2 and sorted(a["grup_idleri"]) == sorted([g1, g2])
    assert await grup_sahibi(g1) == a["id"] and await grup_sahibi(g2) == a["id"]
    async with SessionLocal() as s:
        kayit = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "antrenor_olusturuldu"))).scalar_one()
    assert sorted(kayit.detay["gruplar"]["eklenen"]) == sorted([g1, g2])


async def test_olusturmada_gecersiz_grup_422_ve_hicbir_sey_olusmaz(istemci, yonetici):
    pasif = await grup_ac("Eski", aktif=False)
    sahte = "00000000-0000-0000-0000-000000000000"
    for gid in (pasif, sahte):
        assert (await olustur(istemci, yonetici, grup_idleri=[gid])).status_code == 422
    assert (await istemci.get("/api/antrenorler", headers=yonetici)).json() == []


async def test_grup_idleri_kume_semantigi(istemci, yonetici):
    a = (await olustur(istemci, yonetici)).json()["antrenor"]
    b = (await olustur(istemci, yonetici, ad_soyad="Veli Hoca", telefon="0532 000 00 09")).json()["antrenor"]
    g1, g2, g3 = await grup_ac("A"), await grup_ac("B"), await grup_ac("C", antrenor_id=b["id"])
    # g3 başka antrenörde: bu antrenöre taşınır
    y = await istemci.patch(f"/api/antrenorler/{a['id']}", json={"grup_idleri": [g1, g3]}, headers=yonetici)
    assert y.status_code == 200, y.text
    assert sorted(y.json()["grup_idleri"]) == sorted([g1, g3]) and y.json()["grup_sayisi"] == 2
    assert await grup_sahibi(g3) == a["id"]
    assert [x for x in (await istemci.get("/api/antrenorler", headers=yonetici)).json() if x["id"] == b["id"]][0]["grup_sayisi"] == 0
    # Çıkarılan grubun antrenörü boşalır
    y = await istemci.patch(f"/api/antrenorler/{a['id']}", json={"grup_idleri": [g3, g2]}, headers=yonetici)
    assert sorted(y.json()["grup_idleri"]) == sorted([g3, g2])
    assert await grup_sahibi(g1) is None
    async with SessionLocal() as s:
        kayit = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "antrenor_guncellendi").order_by(DenetimKaydi.id.desc()))).scalars().first()
    assert kayit.detay["gruplar"] == {"eklenen": [g2], "cikarilan": [g1]}
    # Alan yok: dokunulmaz
    y = await istemci.patch(f"/api/antrenorler/{a['id']}", json={"ad_soyad": "Yeni Ad"}, headers=yonetici)
    assert sorted(y.json()["grup_idleri"]) == sorted([g3, g2])
    # Boş liste: hepsi boşalır
    y = await istemci.patch(f"/api/antrenorler/{a['id']}", json={"grup_idleri": []}, headers=yonetici)
    assert y.json()["grup_idleri"] == [] and y.json()["grup_sayisi"] == 0
    assert await grup_sahibi(g2) is None and await grup_sahibi(g3) is None


async def test_grup_idleri_gecersiz_422_ve_atomik(istemci, yonetici):
    a = (await olustur(istemci, yonetici)).json()["antrenor"]
    g1 = await grup_ac("A", antrenor_id=a["id"])
    pasif = await grup_ac("Eski", aktif=False)
    sahte = "00000000-0000-0000-0000-000000000000"
    for gid in (pasif, sahte):
        y = await istemci.patch(
            f"/api/antrenorler/{a['id']}", json={"ad_soyad": "Değişmez", "grup_idleri": [gid]}, headers=yonetici
        )
        assert y.status_code == 422
    assert await grup_sahibi(g1) == a["id"]
    kalici = [x for x in (await istemci.get("/api/antrenorler", headers=yonetici)).json() if x["id"] == a["id"]][0]
    assert kalici["ad_soyad"] == "Ali Hoca"


async def test_gruplar_yalniz_yonetici(istemci, yonetici):
    antrenor = await giris(istemci, "hoca@kulup.com", Rol.antrenor)
    g = await grup_ac("A")
    sahte = "00000000-0000-0000-0000-000000000000"
    assert (await istemci.post("/api/antrenorler", json={"ad_soyad": "X", "telefon": "0532 111 22 33", "grup_idleri": [g]}, headers=antrenor)).status_code == 403
    assert (await istemci.patch(f"/api/antrenorler/{sahte}", json={"grup_idleri": [g]}, headers=antrenor)).status_code == 403
    assert await grup_sahibi(g) is None


async def test_antrenor_kendi_girisini_degistirince_kart_telefonu_esitlenir(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    g = await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": d["gecici_sifre"]})
    baslik = {"Authorization": f"Bearer {g.json()['access_token']}"}
    y = await istemci.patch(
        "/api/auth/giris", json={"yeni_giris": "0532 444 33 22", "sifre": d["gecici_sifre"]}, headers=baslik
    )
    assert y.status_code == 200, y.text
    kart = [a for a in (await istemci.get("/api/antrenorler", headers=yonetici)).json() if a["id"] == d["antrenor"]["id"]][0]
    assert kart["giris"] == "+905324443322" and kart["telefon"] == "+905324443322"


async def test_yalniz_ad_degisince_giris_ve_oturumlar_degismez(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    aid = d["antrenor"]["id"]
    await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": d["gecici_sifre"]})
    y = await istemci.patch(f"/api/antrenorler/{aid}", json={"ad_soyad": "Yeni Ad"}, headers=yonetici)
    assert y.status_code == 200, y.text
    assert y.json()["giris"] == "+905320000000"
    async with SessionLocal() as s:
        k = (await s.execute(select(Kullanici).where(Kullanici.giris == "+905320000000"))).scalar_one()
        assert (await s.execute(select(Oturum).where(Oturum.kullanici_id == k.id, Oturum.iptal.is_(False)))).first() is not None
        kayit = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "antrenor_guncellendi"))).scalar_one()
    assert kayit.detay == {"alanlar": ["ad_soyad"]}


async def test_antrenor_girisini_eposta_yapamaz(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    g = await istemci.post("/api/auth/login", json={"giris": "+905320000000", "sifre": d["gecici_sifre"]})
    baslik = {"Authorization": f"Bearer {g.json()['access_token']}"}
    y = await istemci.patch(
        "/api/auth/giris", json={"yeni_giris": "hoca@kulup.com", "sifre": d["gecici_sifre"]}, headers=baslik
    )
    assert y.status_code == 422, y.text
    assert "telefon" in y.json()["detail"]


async def test_guncelle_denetim_detayi(istemci, yonetici):
    a = (await olustur(istemci, yonetici)).json()["antrenor"]
    b = (await olustur(istemci, yonetici, ad_soyad="Veli Hoca", telefon="0532 000 00 09")).json()["antrenor"]
    g = await grup_ac("C", antrenor_id=b["id"])
    y = await istemci.patch(
        f"/api/antrenorler/{a['id']}",
        json={"ad_soyad": "Ali Hoca", "telefon": "0533 111 22 33", "grup_idleri": [g, g]},
        headers=yonetici,
    )
    assert y.status_code == 200, y.text
    async with SessionLocal() as s:
        kayit = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "antrenor_guncellendi"))).scalar_one()
    assert kayit.detay["alanlar"] == ["grup_idleri", "telefon"]
    assert kayit.detay["giris_degisti"] is True and kayit.detay["oturumlar_kapatildi"] is True
    assert kayit.detay["gruplar"]["onceki_antrenor"] == {g: b["id"]}
    assert "533" not in json.dumps(kayit.detay)
