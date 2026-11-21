"""Antrenör profil fotoğrafı: yalnız yönetici yükler; görüntüleme yetkisi sunucuda denetlenir."""
import io
from datetime import date

from PIL import Image
from sqlalchemy import select

from app.db import SessionLocal
from app.depolama import depolama
from app.models import AntrenorFotoRizasi, DenetimKaydi, Rol
from tests.conftest import destek_baslik
from tests.test_veli_paneli import baslik as veli_baslik, veli_ve_cocuk
from tests.test_yoklama import antrenor_hesabi, giris, grup_olustur, ogrenci_olustur, uye_yap


def resim(boyut=(600, 400)):
    c = io.BytesIO()
    Image.new("RGB", boyut, (20, 120, 200)).save(c, "JPEG")
    return c.getvalue()


def dosya(veri=None):
    return {"dosya": ("a.jpg", veri or resim(), "image/jpeg")}


async def yukle(istemci, baslik, antrenor, veri=None, riza=True):
    """Yükleme; riza=True ise önce rıza kaydı (yoksa) doğrudan veritabanına eklenir."""
    if riza:
        async with SessionLocal() as s:
            if (await s.execute(select(AntrenorFotoRizasi).where(
                AntrenorFotoRizasi.antrenor_id == antrenor.id, AntrenorFotoRizasi.geri_cekildi.is_(None)
            ))).first() is None:
                s.add(AntrenorFotoRizasi(antrenor_id=antrenor.id))
                await s.commit()
    return await istemci.post(f"/api/antrenorler/{antrenor.id}/foto", files=dosya(veri), headers=baslik)


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
    assert k.headers["cache-control"] == "private, no-cache"
    assert (await istemci.get(url, headers={**yonetici, "If-None-Match": k.headers["etag"]})).status_code == 304
    liste = (await istemci.get("/api/antrenorler", headers=yonetici)).json()
    assert liste[0]["foto_var"] is True
    assert (await istemci.delete(url, headers=yonetici)).status_code == 204
    assert (await istemci.get(url, headers=yonetici)).status_code == 404
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi))).scalars().all()
    yuklenen = [k for k in kayitlar if k.islem == "antrenor_foto_yuklendi"]
    assert yuklenen and not yuklenen[0].detay
    assert any(k.islem == "antrenor_foto_silindi" for k in kayitlar)


async def test_rizasiz_yukleme_409_ve_gecersiz_dosya(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    assert (await yukle(istemci, yonetici, antrenor, riza=False)).status_code == 409
    await istemci.post(f"/api/antrenorler/{antrenor.id}/foto-riza", headers=yonetici)
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


async def test_baska_antrenor_gorur(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    diger_baslik, _ = await antrenor_hesabi(istemci, "+905320000011", "Veli Hoca")
    await yukle(istemci, yonetici, antrenor)
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=diger_baslik)).status_code == 200


async def test_veli_baska_antrenorun_fotosunu_de_gorur(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    _, baska = await antrenor_hesabi(istemci, "+905320000012", "Baska Hoca")
    await yukle(istemci, yonetici, antrenor)
    await yukle(istemci, yonetici, baska)
    _, cocuk = await veli_ve_cocuk()
    grup = await grup_olustur("U10", antrenor)
    await uye_yap(cocuk, grup)
    vb = await veli_baslik(istemci)
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=vb)).status_code == 200
    assert (await istemci.get(f"/api/antrenorler/{baska.id}/foto", headers=vb)).status_code == 200
    # yazma yetkisi yok
    assert (await yukle(istemci, vb, antrenor)).status_code == 403


async def test_veli_gruptan_ayrilmis_ve_baskasinin_cocugu_yine_gorur(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    await yukle(istemci, yonetici, antrenor)
    _, cocuk = await veli_ve_cocuk()
    grup = await grup_olustur("U10", antrenor)
    await uye_yap(cocuk, grup, bitis=date(2020, 6, 1))
    vb = await veli_baslik(istemci)
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=vb)).status_code == 200
    # başka velinin çocuğu aynı grupta: yine görür
    k2, _ = await veli_ve_cocuk(giris="+905559998877", ad="Zeynep")
    d = await ogrenci_olustur("Baska", "Cocuk")
    await uye_yap(d, grup)
    vb2 = await veli_baslik(istemci, "+905559998877")
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=vb2)).status_code == 200


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


async def test_riza_ver_idempotent_ve_listede(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    url = f"/api/antrenorler/{antrenor.id}/foto-riza"
    assert (await istemci.get("/api/antrenorler", headers=yonetici)).json()[0]["foto_rizasi"] is None
    r1 = await istemci.post(url, headers=yonetici)
    r2 = await istemci.post(url, headers=yonetici)
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["foto_rizasi"] is not None and r1.json()["foto_rizasi"] == r2.json()["foto_rizasi"]
    assert (await istemci.get("/api/antrenorler", headers=yonetici)).json()[0]["foto_rizasi"] == r1.json()["foto_rizasi"]
    async with SessionLocal() as s:
        verildi = [k for k in (await s.execute(select(DenetimKaydi))).scalars() if k.islem == "antrenor_foto_rizasi_verildi"]
    assert len(verildi) == 1


async def test_riza_geri_cekme_fotoyu_ve_dosyayi_siler(istemci):
    from app.models import Antrenor

    yonetici, _, antrenor = await hazirla(istemci)
    assert (await yukle(istemci, yonetici, antrenor)).status_code == 204
    async with SessionLocal() as s:
        anahtar = (await s.get(Antrenor, antrenor.id)).foto_anahtar
    assert depolama.oku(anahtar, "kucuk") is not None
    r = await istemci.delete(f"/api/antrenorler/{antrenor.id}/foto-riza", headers=yonetici)
    assert r.status_code == 200 and r.json()["foto_rizasi"] is None and r.json()["foto_var"] is False
    assert depolama.oku(anahtar, "kucuk") is None
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=yonetici)).status_code == 404
    async with SessionLocal() as s:
        kayit = [k for k in (await s.execute(select(DenetimKaydi))).scalars() if k.islem == "antrenor_foto_rizasi_geri_cekildi"]
    assert len(kayit) == 1 and kayit[0].detay == {"foto_silindi": True}
    # rıza yokken tekrar: yine 200, yeni denetim kaydı yok
    assert (await istemci.delete(f"/api/antrenorler/{antrenor.id}/foto-riza", headers=yonetici)).status_code == 200
    assert (await yukle(istemci, yonetici, antrenor, riza=False)).status_code == 409


async def test_yonetici_olmayan_riza_veremez_geri_cekemez(istemci):
    yonetici, ant_baslik, antrenor = await hazirla(istemci)
    url = f"/api/antrenorler/{antrenor.id}/foto-riza"
    assert (await istemci.post(url, headers=ant_baslik)).status_code == 403
    await istemci.post(url, headers=yonetici)
    assert (await istemci.delete(url, headers=ant_baslik)).status_code == 403
    _, _ = await veli_ve_cocuk()
    vb = await veli_baslik(istemci)
    assert (await istemci.post(url, headers=vb)).status_code == 403
    assert (await istemci.delete(url, headers=vb)).status_code == 403


async def test_pasif_antrenor_fotosu_kalir(istemci):
    yonetici, _, antrenor = await hazirla(istemci)
    await yukle(istemci, yonetici, antrenor)
    r = await istemci.patch(f"/api/antrenorler/{antrenor.id}", json={"aktif": False}, headers=yonetici)
    assert r.status_code == 200 and r.json()["aktif"] is False and r.json()["foto_var"] is True
    assert (await istemci.get(f"/api/antrenorler/{antrenor.id}/foto", headers=yonetici)).status_code == 200
