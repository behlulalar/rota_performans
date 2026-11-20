"""Antrenör profil fotoğrafı: yalnız yönetici yükler; görüntüleme yetkisi sunucuda denetlenir."""
import io
from datetime import date

from PIL import Image
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DenetimKaydi, Rol
from tests.conftest import destek_baslik
from tests.test_veli_paneli import baslik as veli_baslik, veli_ve_cocuk
from tests.test_yoklama import antrenor_hesabi, giris, grup_olustur, ogrenci_olustur, uye_yap


def resim(boyut=(600, 400)):
    c = io.BytesIO()
    Image.new("RGB", boyut, (20, 120, 200)).save(c, "JPEG")
    return c.getvalue()


def dosya(veri=None):
    return {"dosya": ("a.jpg", veri or resim(), "image/jpeg")}


async def yukle(istemci, baslik, antrenor, onay="true", veri=None):
    return await istemci.post(
        f"/api/antrenorler/{antrenor.id}/foto", files=dosya(veri), data={"onay": onay}, headers=baslik
    )


async def hazirla(istemci):
    yonetici = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    ant_baslik, antrenor = await antrenor_hesabi(istemci, "+905320000010", "Ali Hoca")
    return yonetici, ant_baslik, antrenor


async def test_yukleme_isleme_ve_denetim(istemci):
    yonetici, ant_baslik, antrenor = await hazirla(istemci)
    url = f"/api/antrenorler/{antrenor.id}/foto"
    assert (await istemci.get(url, headers=yonetici)).status_code == 404
    assert (await yukle(istemci, yonetici, antrenor)).status_code == 204
    k = await istemci.get(url, headers=yonetici)
    b = await istemci.get(url + "?boyut=buyuk", headers=yonetici)
    assert Image.open(io.BytesIO(k.content)).size == (160, 160)
    assert Image.open(io.BytesIO(b.content)).size == (600, 400)
    assert k.headers["cache-control"] == "private, max-age=86400"
    assert (await istemci.get(url, headers={**yonetici, "If-None-Match": k.headers["etag"]})).status_code == 304
    liste = (await istemci.get("/api/antrenorler", headers=yonetici)).json()
    assert liste[0]["foto_var"] is True
    assert (await istemci.delete(url, headers=yonetici)).status_code == 204
    assert (await istemci.get(url, headers=yonetici)).status_code == 404
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi))).scalars().all()
    yuklenen = [k for k in kayitlar if k.islem == "antrenor_foto_yuklendi"]
    assert yuklenen and yuklenen[0].detay == {"antrenor_onayi": True}
    assert any(k.islem == "antrenor_foto_silindi" for k in kayitlar)


async def test_onay_zorunlu_ve_gecersiz_dosya(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    assert (await yukle(istemci, yonetici, antrenor, onay="false")).status_code == 409
    y = await istemci.post(f"/api/antrenorler/{antrenor.id}/foto", files=dosya(), headers=yonetici)
    assert y.status_code == 422
    assert (await yukle(istemci, yonetici, antrenor, veri=b"resim degil")).status_code == 422


async def test_antrenor_kendi_fotosunu_degistiremez(istemci):
    yonetici, ant_baslik, antrenor = await hazirla(istemci)
    assert (await yukle(istemci, ant_baslik, antrenor)).status_code == 403
    await yukle(istemci, yonetici, antrenor)
    assert (await istemci.delete(f"/api/antrenorler/{antrenor.id}/foto", headers=ant_baslik)).status_code == 403
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=ant_baslik)).status_code == 200
    profil = (await istemci.get("/api/antrenor/profil", headers=ant_baslik)).json()
    assert profil["foto_var"] is True and profil["id"] == str(antrenor.id)


async def test_destek_yukleyebilir_ve_gorur(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    d = await destek_baslik(istemci)
    assert (await yukle(istemci, d, antrenor)).status_code == 204
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=d)).status_code == 200


async def test_baska_antrenor_goremez(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    diger_baslik, _ = await antrenor_hesabi(istemci, "+905320000011", "Veli Hoca")
    await yukle(istemci, yonetici, antrenor)
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=diger_baslik)).status_code == 404


async def test_veli_yalniz_cocugunun_antrenorunu_gorur(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    _, baska = await antrenor_hesabi(istemci, "+905320000012", "Baska Hoca")
    await yukle(istemci, yonetici, antrenor)
    await yukle(istemci, yonetici, baska)
    _, cocuk = await veli_ve_cocuk()
    grup = await grup_olustur("U10", antrenor)
    await uye_yap(cocuk, grup)
    vb = await veli_baslik(istemci)
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=vb)).status_code == 200
    # başka antrenör: çocuğun grubunda değil
    assert (await istemci.get(f"/api/antrenorler/{baska.id}/foto", headers=vb)).status_code == 404
    # yazma yetkisi yok
    assert (await yukle(istemci, vb, antrenor)).status_code == 403


async def test_veli_grup_degisince_ve_baskasinin_cocugu(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    await yukle(istemci, yonetici, antrenor)
    _, cocuk = await veli_ve_cocuk()
    grup = await grup_olustur("U10", antrenor)
    # çocuk gruptan ayrılmış: artık görünmez
    await uye_yap(cocuk, grup, bitis=date(2020, 6, 1))
    vb = await veli_baslik(istemci)
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=vb)).status_code == 404
    # başka velinin çocuğu aynı grupta: bu veli göremez
    k2, _ = await veli_ve_cocuk(giris="+905559998877", ad="Zeynep")
    d = await ogrenci_olustur("Baska", "Cocuk")
    await uye_yap(d, grup)
    vb2 = await veli_baslik(istemci, "+905559998877")
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=vb2)).status_code == 404


async def test_ogrenci_hesabi_kendi_antrenorunu_gorur(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    await yukle(istemci, yonetici, antrenor)
    _, ogr = await veli_ve_cocuk(giris="+905557776655", rol=Rol.ogrenci)
    grup = await grup_olustur("U16", antrenor)
    await uye_yap(ogr, grup)
    ob = await veli_baslik(istemci, "+905557776655")
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=ob)).status_code == 200
    d = (await istemci.get(f"/api/benim/cocuklar/{ogr.id}", headers=ob)).json()
    assert d["antrenorler"][0]["foto_var"] is True


async def test_kimlik_dogrulamasiz_ve_olmayan(istemci):
    import uuid

    yonetici, _, antrenor = await hazirla(istemci)
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto")).status_code == 401
    assert (await istemci.get(f"/api/antrenorler/{uuid.uuid4()}/foto", headers=yonetici)).status_code == 404


async def test_veli_cocuk_detayinda_yalniz_ad_ve_foto(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    await yukle(istemci, yonetici, antrenor)
    _, cocuk = await veli_ve_cocuk()
    await uye_yap(cocuk, await grup_olustur("U10", antrenor))
    await uye_yap(cocuk, await grup_olustur("U12", antrenor))  # aynı antrenör iki grupta: tek kayıt
    vb = await veli_baslik(istemci)
    d = (await istemci.get(f"/api/benim/cocuklar/{cocuk.id}", headers=vb)).json()
    assert d["antrenorler"] == [{"id": str(antrenor.id), "ad_soyad": "Ali Hoca", "foto_var": True}]
    assert "+9053" not in str(d["antrenorler"])


async def test_me_antrenor_id_ve_foto_var(istemci):
    yonetici, ant_baslik, antrenor = await hazirla(istemci)
    ben = (await istemci.get("/api/auth/me", headers=ant_baslik)).json()
    assert ben["antrenor_id"] == str(antrenor.id) and ben["foto_var"] is False
    await yukle(istemci, yonetici, antrenor)
    assert (await istemci.get("/api/auth/me", headers=ant_baslik)).json()["foto_var"] is True
    assert (await istemci.get("/api/auth/me", headers=yonetici)).json()["antrenor_id"] is None
