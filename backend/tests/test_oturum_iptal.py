"""Dersi iptal et / geri al (yönetici): kurallar, telafi planlarının silinmesi, oturum üretiminin iptali geri açmaması."""
import uuid
from datetime import time, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DenetimKaydi, DersOturumu, OturumDurum, Rol, TelafiPlani
from tests.test_telafi import detay, hakli_ogrenci, planla
from tests.test_yoklama import (
    BUGUN,
    antrenor_hesabi,
    giris,
    govde,
    grup_olustur,
    ogrenci_olustur,
    oturum_olustur,
    uye_yap,
    yonetici,  # noqa: F401  (fixture)
)


def iptal_url(ot):
    return f"/api/oturumlar/{ot.id}/iptal"


async def durum_oku(ot_id):
    async with SessionLocal() as s:
        return (await s.get(DersOturumu, ot_id)).durum


async def test_yetki(istemci, yonetici):
    g = await grup_olustur()
    ot = await oturum_olustur(g, BUGUN + timedelta(days=2))
    assert (await istemci.post(iptal_url(ot))).status_code == 401
    assert (await istemci.post(f"/api/oturumlar/{ot.id}/geri-al")).status_code == 401
    antrenor, _ = await antrenor_hesabi(istemci, "antrenor@kulup.com", "Ant")
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    for baslik in (antrenor, veli):
        assert (await istemci.post(iptal_url(ot), headers=baslik)).status_code == 403
        assert (await istemci.post(f"/api/oturumlar/{ot.id}/geri-al", headers=baslik)).status_code == 403
    assert await durum_oku(ot.id) == OturumDurum.planli


async def test_iptal_basarili_ve_denetim_kaydi(istemci, yonetici):
    g = await grup_olustur()
    ot = await oturum_olustur(g, BUGUN + timedelta(days=2))
    y = await istemci.post(iptal_url(ot), json={"neden": "Salon kapalı"}, headers=yonetici)
    assert y.status_code == 200 and y.json()["durum"] == "iptal"
    assert await durum_oku(ot.id) == OturumDurum.iptal
    async with SessionLocal() as s:
        kayit = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "oturum_iptal_edildi"))).scalar_one()
    assert kayit.hedef_id == str(ot.id) and kayit.detay["neden"] == "Salon kapalı"
    # Gövdesiz çağrı da geçerli (zaten iptal -> 409).
    assert (await istemci.post(iptal_url(ot), headers=yonetici)).status_code == 409


async def test_govdesiz_iptal(istemci, yonetici):
    g = await grup_olustur()
    ot = await oturum_olustur(g, BUGUN + timedelta(days=2))
    assert (await istemci.post(iptal_url(ot), headers=yonetici)).status_code == 200


async def test_bulunamayan_oturum_404(istemci, yonetici):
    assert (await istemci.post(f"/api/oturumlar/{uuid.uuid4()}/iptal", headers=yonetici)).status_code == 404


async def test_yoklamasi_alinmis_ders_iptal_edilemez(istemci, yonetici):
    g = await grup_olustur()
    o = await ogrenci_olustur()
    await uye_yap(o, g)
    ot = await oturum_olustur(g, BUGUN)
    assert (await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o, "geldi")), headers=yonetici)).status_code == 200
    y = await istemci.post(iptal_url(ot), headers=yonetici)
    assert y.status_code == 409 and "Yoklaması alınmış" in y.json()["detail"]
    assert await durum_oku(ot.id) == OturumDurum.planli


async def test_yapildi_durumundaki_ders_iptal_edilemez(istemci, yonetici):
    g = await grup_olustur()
    ot = await oturum_olustur(g, BUGUN - timedelta(days=1), durum=OturumDurum.yapildi)
    assert (await istemci.post(iptal_url(ot), headers=yonetici)).status_code == 409


async def test_iptal_edilmis_derse_yoklama_alinamaz(istemci, yonetici):
    g = await grup_olustur()
    o = await ogrenci_olustur()
    await uye_yap(o, g)
    ot = await oturum_olustur(g, BUGUN)
    assert (await istemci.post(iptal_url(ot), headers=yonetici)).status_code == 200
    y = await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o, "geldi")), headers=yonetici)
    assert y.status_code == 422


async def test_telafi_planlari_silinir_ve_hak_yeniden_planlanabilir(istemci, yonetici):
    g = await grup_olustur()
    ot = await oturum_olustur(g, BUGUN + timedelta(days=2))
    o = await hakli_ogrenci(istemci, yonetici)
    assert (await planla(istemci, yonetici, ot, o)).status_code == 200
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 0

    assert (await istemci.post(iptal_url(ot), headers=yonetici)).status_code == 200
    async with SessionLocal() as s:
        assert (await s.execute(select(TelafiPlani).where(TelafiPlani.oturum_id == ot.id))).first() is None
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 1
    # Hak başka derse yeniden planlanabilir.
    ot2 = await oturum_olustur(g, BUGUN + timedelta(days=3))
    assert (await planla(istemci, yonetici, ot2, o)).status_code == 200


async def test_uretim_iptal_edilmis_oturumu_yeniden_acmaz(istemci, yonetici):
    gun = BUGUN.isoweekday()
    g = await grup_olustur(program=((gun, time(17), time(18, 30)),))
    aralik = {"baslangic": str(BUGUN), "bitis": str(BUGUN)}
    assert (await istemci.post("/api/oturumlar/uret", json=aralik, headers=yonetici)).json() == {"olusturulan": 1}
    async with SessionLocal() as s:
        ot = (await s.execute(select(DersOturumu).where(DersOturumu.grup_id == g.id))).scalar_one()
    assert (await istemci.post(iptal_url(ot), headers=yonetici)).status_code == 200
    assert (await istemci.post("/api/oturumlar/uret", json=aralik, headers=yonetici)).json() == {"olusturulan": 0}
    async with SessionLocal() as s:
        oturumlar = list((await s.execute(select(DersOturumu).where(DersOturumu.grup_id == g.id))).scalars())
    assert len(oturumlar) == 1 and oturumlar[0].durum == OturumDurum.iptal


async def test_geri_al(istemci, yonetici):
    g = await grup_olustur()
    gelecek = await oturum_olustur(g, BUGUN + timedelta(days=2))
    gecmis = await oturum_olustur(g, BUGUN - timedelta(days=2), durum=OturumDurum.iptal, baslangic=time(3))
    planli = await oturum_olustur(g, BUGUN + timedelta(days=4))
    # İptal edilmemiş ders geri alınamaz.
    assert (await istemci.post(f"/api/oturumlar/{planli.id}/geri-al", headers=yonetici)).status_code == 409
    assert (await istemci.post(iptal_url(gelecek), headers=yonetici)).status_code == 200
    y = await istemci.post(f"/api/oturumlar/{gelecek.id}/geri-al", headers=yonetici)
    assert y.status_code == 200 and y.json()["durum"] == "planli"
    # Geçmiş tarihli iptal geri alınamaz.
    assert (await istemci.post(f"/api/oturumlar/{gecmis.id}/geri-al", headers=yonetici)).status_code == 422
    assert await durum_oku(gecmis.id) == OturumDurum.iptal
