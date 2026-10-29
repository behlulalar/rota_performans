import json

import pytest
from sqlalchemy import select

from app.api.auth import COOKIE_ADI
from app.db import SessionLocal
from app.models import DenetimKaydi, Kullanici, Oturum, Rol
from tests.conftest import SIFRE, kullanici_olustur

URL = "/api/yoneticiler"


async def login(istemci, giris, sifre=SIFRE):
    y = await istemci.post("/api/auth/login", json={"giris": giris, "sifre": sifre})
    assert y.status_code == 200, y.text
    return {"Authorization": f"Bearer {y.json()['access_token']}"}


async def giris(istemci, eposta, rol):
    k = await kullanici_olustur(eposta, rol)
    return await login(istemci, eposta), k


@pytest.fixture
async def yonetici(istemci):
    baslik, k = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    baslik["_id"] = str(k.id)  # yalnız testte kimliğe erişmek için; başlık olarak gönderilmez
    return baslik


def h(baslik):
    return {k: v for k, v in baslik.items() if not k.startswith("_")}


async def olustur(istemci, baslik, **ek):
    govde = {"ad_soyad": "ayşe yılmaz", "giris": "ayse@kulup.com"}
    govde.update(ek)
    return await istemci.post(URL, json=govde, headers=h(baslik))


async def kayit(giris_):
    async with SessionLocal() as s:
        return (await s.execute(select(Kullanici).where(Kullanici.giris == giris_))).scalar_one()


async def aktif_oturum_sayisi(kullanici_id):
    async with SessionLocal() as s:
        return len(
            (await s.execute(select(Oturum).where(Oturum.kullanici_id == kullanici_id, Oturum.iptal.is_(False))))
            .scalars()
            .all()
        )


async def test_yetki_401_403(istemci, yonetici):
    assert (await istemci.get(URL)).status_code == 401
    assert (await istemci.post(URL, json={"ad_soyad": "A", "giris": "a@b.com"})).status_code == 401
    for eposta, rol in [("hoca@kulup.com", Rol.antrenor), ("veli@kulup.com", Rol.veli)]:
        b, _ = await giris(istemci, eposta, rol)
        assert (await istemci.get(URL, headers=b)).status_code == 403
        assert (await istemci.post(URL, json={"ad_soyad": "A", "giris": "a@b.com"}, headers=b)).status_code == 403
        assert (await istemci.patch(f"{URL}/{yonetici['_id']}", json={"aktif": False}, headers=b)).status_code == 403
        assert (await istemci.post(f"{URL}/{yonetici['_id']}/sifre-sifirla", headers=b)).status_code == 403


async def test_olustur_listele_ve_gecici_sifre(istemci, yonetici):
    y = await olustur(istemci, yonetici, giris="AYSE@Kulup.com ")
    assert y.status_code == 201, y.text
    d = y.json()
    sifre = d["gecici_sifre"]
    assert d["yonetici"]["giris"] == "ayse@kulup.com"
    assert d["yonetici"]["ad_soyad"] == "Ayşe Yılmaz"
    assert d["yonetici"]["aktif"] is True and d["yonetici"]["ben"] is False
    assert (await kayit("ayse@kulup.com")).sifre_degistirmeli is True

    liste = (await istemci.get(URL, headers=h(yonetici))).json()
    assert {x["giris"] for x in liste} == {"yonetici@kulup.com", "ayse@kulup.com"}
    assert [x["ben"] for x in liste if x["giris"] == "yonetici@kulup.com"] == [True]
    assert all({"id", "ad_soyad", "giris", "aktif", "son_giris", "olusturma", "ben"} <= set(x) for x in liste)

    # Yeni yönetici geçici şifreyle girer ama yönetici uç noktaları şifre değişene kadar kapalı.
    yeni = await login(istemci, "ayse@kulup.com", sifre)
    assert (await istemci.get(URL, headers=yeni)).status_code == 403
    me = await istemci.get("/api/auth/me", headers=yeni)
    assert me.json()["rol"] == "admin" and me.json()["sifre_degistirmeli"] is True


async def test_telefon_normalize(istemci, yonetici):
    y = await olustur(istemci, yonetici, giris="0532 111 22 33")
    assert y.status_code == 201
    assert y.json()["yonetici"]["giris"] == "+905321112233"
    await login(istemci, "05321112233", y.json()["gecici_sifre"])
    # Geçersiz giriş
    assert (await olustur(istemci, yonetici, giris="123")).status_code == 422
    assert (await olustur(istemci, yonetici, giris="a@@b")).status_code == 422
    # Aynı numara başka biçimde yazılınca da tekrar sayılır
    assert (await olustur(istemci, yonetici, giris="+90 532 111 22 33")).status_code == 409


async def test_giris_tekrar_409_tum_roller(istemci, yonetici):
    await kullanici_olustur("hoca@kulup.com", Rol.antrenor)
    await kullanici_olustur("veli@kulup.com", Rol.veli)
    for g in ["yonetici@kulup.com", "HOCA@kulup.com", "veli@kulup.com"]:
        y = await olustur(istemci, yonetici, giris=g)
        assert y.status_code == 409, g
        assert y.json()["detail"] == "Bu giriş bilgisi başka bir hesapta kayıtlı"
    ok = (await olustur(istemci, yonetici)).json()["yonetici"]["id"]
    # Güncellemede de aynı kural
    for g in ["hoca@kulup.com", "veli@kulup.com", "yonetici@kulup.com"]:
        assert (await istemci.patch(f"{URL}/{ok}", json={"giris": g}, headers=h(yonetici))).status_code == 409


async def test_patch_ad_giris_ve_oturum_iptali(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    yid = d["yonetici"]["id"]
    await login(istemci, "ayse@kulup.com", d["gecici_sifre"])
    k = await kayit("ayse@kulup.com")
    assert await aktif_oturum_sayisi(k.id) == 1

    y = await istemci.patch(f"{URL}/{yid}", json={"ad_soyad": "fatma kaya"}, headers=h(yonetici))
    assert y.status_code == 200 and y.json()["ad_soyad"] == "Fatma Kaya"
    assert await aktif_oturum_sayisi(k.id) == 1  # ad değişince oturum kalır

    y = await istemci.patch(f"{URL}/{yid}", json={"giris": "Fatma@Kulup.com"}, headers=h(yonetici))
    assert y.status_code == 200 and y.json()["giris"] == "fatma@kulup.com"
    assert await aktif_oturum_sayisi(k.id) == 0
    # Eski giriş geçersiz, yenisi çalışır
    assert (await istemci.post("/api/auth/login", json={"giris": "ayse@kulup.com", "sifre": d["gecici_sifre"]})).status_code == 401
    await login(istemci, "fatma@kulup.com", d["gecici_sifre"])

    assert (await istemci.patch(f"{URL}/{yid}", json={"ad_soyad": None}, headers=h(yonetici))).status_code == 422
    assert (await istemci.patch(f"{URL}/{yid}", json={"giris": "x"}, headers=h(yonetici))).status_code == 422


async def test_bulunamayan_ve_baska_rol_404(istemci, yonetici):
    import uuid

    veli = await kullanici_olustur("veli@kulup.com", Rol.veli)
    for kimlik in [uuid.uuid4(), veli.id]:
        assert (await istemci.patch(f"{URL}/{kimlik}", json={"aktif": False}, headers=h(yonetici))).status_code == 404
        assert (await istemci.post(f"{URL}/{kimlik}/sifre-sifirla", headers=h(yonetici))).status_code == 404


async def test_pasife_alma_oturumlari_kapatir_ve_girisi_engeller(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    yid = d["yonetici"]["id"]
    yeni = await login(istemci, "ayse@kulup.com", d["gecici_sifre"])
    k = await kayit("ayse@kulup.com")
    y = await istemci.patch(f"{URL}/{yid}", json={"aktif": False}, headers=h(yonetici))
    assert y.status_code == 200 and y.json()["aktif"] is False
    assert await aktif_oturum_sayisi(k.id) == 0
    assert (await istemci.get("/api/auth/me", headers=yeni)).status_code in (401, 403)
    assert (await istemci.post("/api/auth/login", json={"giris": "ayse@kulup.com", "sifre": d["gecici_sifre"]})).status_code == 401
    # Tekrar aktif
    y = await istemci.patch(f"{URL}/{yid}", json={"aktif": True}, headers=h(yonetici))
    assert y.json()["aktif"] is True
    await login(istemci, "ayse@kulup.com", d["gecici_sifre"])


async def test_kendini_pasife_alamaz(istemci, yonetici):
    # Başka aktif yönetici varken: 422
    await olustur(istemci, yonetici)
    y = await istemci.patch(f"{URL}/{yonetici['_id']}", json={"aktif": False}, headers=h(yonetici))
    assert y.status_code == 422
    assert "Kendi hesabınızı" in y.json()["detail"]
    assert (await kayit("yonetici@kulup.com")).aktif is True
    # Kendi adı değişebilir, aktif=True zararsız
    y = await istemci.patch(f"{URL}/{yonetici['_id']}", json={"ad_soyad": "Ana Yönetici", "aktif": True}, headers=h(yonetici))
    assert y.status_code == 200 and y.json()["ben"] is True


async def test_son_aktif_yonetici_korunur(istemci, yonetici):
    y = await istemci.patch(f"{URL}/{yonetici['_id']}", json={"aktif": False}, headers=h(yonetici))
    assert y.status_code == 409
    assert y.json()["detail"] == "Son aktif yönetici pasife alınamaz"
    assert (await kayit("yonetici@kulup.com")).aktif is True


async def test_baskasinin_giris_degisimi_ama_kendi_giris_ve_sifre_degil(istemci, yonetici):
    y = await istemci.patch(f"{URL}/{yonetici['_id']}", json={"giris": "yeni@kulup.com"}, headers=h(yonetici))
    assert y.status_code == 422
    assert (await kayit("yonetici@kulup.com")).giris == "yonetici@kulup.com"
    y = await istemci.post(f"{URL}/{yonetici['_id']}/sifre-sifirla", headers=h(yonetici))
    assert y.status_code == 422
    # Aynı değeri yollamak zararsız
    y = await istemci.patch(f"{URL}/{yonetici['_id']}", json={"giris": "YONETICI@kulup.com"}, headers=h(yonetici))
    assert y.status_code == 200


async def test_sifre_sifirla_oturumlari_kapatir(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    yid = d["yonetici"]["id"]
    await login(istemci, "ayse@kulup.com", d["gecici_sifre"])
    k = await kayit("ayse@kulup.com")
    assert await aktif_oturum_sayisi(k.id) == 1
    y = await istemci.post(f"{URL}/{yid}/sifre-sifirla", headers=h(yonetici))
    assert y.status_code == 200
    yeni = y.json()["gecici_sifre"]
    assert yeni != d["gecici_sifre"]
    assert await aktif_oturum_sayisi(k.id) == 0
    assert (await istemci.post("/api/auth/login", json={"giris": "ayse@kulup.com", "sifre": d["gecici_sifre"]})).status_code == 401
    await login(istemci, "ayse@kulup.com", yeni)
    assert (await kayit("ayse@kulup.com")).sifre_degistirmeli is True


async def test_denetim_kaydinda_sir_yok(istemci, yonetici):
    d = (await olustur(istemci, yonetici)).json()
    yid = d["yonetici"]["id"]
    await istemci.patch(f"{URL}/{yid}", json={"giris": "baska@kulup.com", "aktif": False}, headers=h(yonetici))
    s2 = (await istemci.post(f"{URL}/{yid}/sifre-sifirla", headers=h(yonetici))).json()["gecici_sifre"]
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi))).scalars().all()
    islemler = {k.islem for k in kayitlar}
    assert {"yonetici_olusturuldu", "yonetici_guncellendi", "yonetici_sifre_sifirlandi"} <= islemler
    metin = json.dumps([[k.islem, k.detay, k.hedef_id, k.hedef_tur] for k in kayitlar])
    for sir in [d["gecici_sifre"], s2, "baska@kulup.com", "ayse@kulup.com"]:
        assert sir not in metin
    assert all(k.kullanici_id == __import__("uuid").UUID(yonetici["_id"]) for k in kayitlar if k.islem.startswith("yonetici_"))


# --- Kendi girişini değiştirme: PATCH /api/auth/giris ---

GIRIS_URL = "/api/auth/giris"


async def test_kendi_girisini_degistirme(istemci):
    h1, k = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    diger = istemci.cookies.get(COOKIE_ADI)
    await login(istemci, "yonetici@kulup.com")  # ikinci cihaz; çerez bu oturumun olur
    h2 = await login(istemci, "yonetici@kulup.com")
    assert diger != istemci.cookies.get(COOKIE_ADI)
    assert await aktif_oturum_sayisi(k.id) == 3

    y = await istemci.patch(GIRIS_URL, json={"yeni_giris": " Yeni@Kulup.com ", "sifre": SIFRE}, headers=h2)
    assert y.status_code == 200, y.text
    assert y.json()["giris"] == "yeni@kulup.com"
    assert await aktif_oturum_sayisi(k.id) == 1  # yalnız bu oturum kalır
    assert (await istemci.post("/api/auth/refresh")).status_code == 200
    assert (await istemci.get("/api/auth/me", headers=h2)).json()["giris"] == "yeni@kulup.com"
    # Eski giriş geçersiz, yenisi çalışır
    assert (await istemci.post("/api/auth/login", json={"giris": "yonetici@kulup.com", "sifre": SIFRE})).status_code == 401
    await login(istemci, "yeni@kulup.com")
    async with SessionLocal() as s:
        kayit_ = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "giris_degisti"))).scalar_one()
    assert kayit_.kullanici_id == k.id
    metin = json.dumps([kayit_.detay, kayit_.hedef_id])
    assert "yeni@kulup.com" not in metin and SIFRE not in metin


async def test_giris_degistirme_telefon_normalize(istemci):
    b, _ = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    y = await istemci.patch(GIRIS_URL, json={"yeni_giris": "0532 111 22 33", "sifre": SIFRE}, headers=b)
    assert y.status_code == 200 and y.json()["giris"] == "+905321112233"
    await login(istemci, "05321112233")


async def test_giris_degistirme_hatalar(istemci):
    b, k = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    await kullanici_olustur("hoca@kulup.com", Rol.antrenor)
    await kullanici_olustur("veli@kulup.com", Rol.veli)
    # Yanlış şifre: 400, genel mesaj, giriş değişmez
    y = await istemci.patch(GIRIS_URL, json={"yeni_giris": "yeni@kulup.com", "sifre": "yanlis-sifre-1"}, headers=b)
    assert y.status_code == 400 and y.json()["detail"] == "Şifre hatalı"
    assert (await kayit("yonetici@kulup.com")).basarisiz_deneme == 1
    # Başka hesabın girişi: 409
    for g in ["hoca@kulup.com", "VELI@kulup.com"]:
        y = await istemci.patch(GIRIS_URL, json={"yeni_giris": g, "sifre": SIFRE}, headers=b)
        assert y.status_code == 409, g
    # Aynı giriş / geçersiz giriş: 422
    for g in ["yonetici@kulup.com", "abc", "a@@b"]:
        y = await istemci.patch(GIRIS_URL, json={"yeni_giris": g, "sifre": SIFRE}, headers=b)
        assert y.status_code == 422, g
    assert (await kayit("yonetici@kulup.com")).giris == "yonetici@kulup.com"
    assert (await istemci.patch(GIRIS_URL, json={"yeni_giris": "x@y.com", "sifre": SIFRE})).status_code == 401


async def test_giris_degistirme_kilit(istemci):
    b, _ = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    for _ in range(5):
        y = await istemci.patch(GIRIS_URL, json={"yeni_giris": "yeni@kulup.com", "sifre": "yanlis-sifre-1"}, headers=b)
        assert y.status_code == 400
    y = await istemci.patch(GIRIS_URL, json={"yeni_giris": "yeni@kulup.com", "sifre": SIFRE}, headers=b)
    assert y.status_code == 401


async def test_giris_degistirme_roller(istemci):
    b, _ = await giris(istemci, "hoca@kulup.com", Rol.antrenor)
    y = await istemci.patch(GIRIS_URL, json={"yeni_giris": "hoca2@kulup.com", "sifre": SIFRE}, headers=b)
    assert y.status_code == 200 and y.json()["giris"] == "hoca2@kulup.com"
    v, _ = await giris(istemci, "veli@kulup.com", Rol.veli)
    y = await istemci.patch(GIRIS_URL, json={"yeni_giris": "veli2@kulup.com", "sifre": SIFRE}, headers=v)
    assert y.status_code == 403
    assert (await kayit("veli@kulup.com")).giris == "veli@kulup.com"
