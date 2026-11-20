"""Antrenör için yoklama kilidi: ilk kayıttan 60 dk sonra yalnız yönetici düzeltebilir."""
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import DenetimKaydi, DersOturumu, Rol, Yoklama
from app.oturumlar import simdi
from tests.test_yoklama import (
    antrenor_hesabi,
    giris,
    govde,
    grup_olustur,
    ogrenci_olustur,
    oturum_olustur,
    uye_yap,
)

MESAJ = "Yoklama kilitlendi. Düzeltme için yöneticiye başvurun."


@pytest.fixture
async def kurulum(istemci):
    ba, a = await antrenor_hesabi(istemci, "hoca@kulup.com", "Hoca")
    g = await grup_olustur("U10", a)
    ot = await oturum_olustur(g)
    o1, o2 = await ogrenci_olustur("Ali"), await ogrenci_olustur("Veli")
    await uye_yap(o1, g)
    await uye_yap(o2, g)
    yon = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    return ba, yon, ot, o1, o2


async def ilk_kayit(oturum_id):
    async with SessionLocal() as s:
        return (await s.execute(select(DersOturumu.yoklama_ilk_kayit).where(DersOturumu.id == oturum_id))).scalar_one()


async def kilidi_gecir(oturum_id, dakika=61):
    async with SessionLocal() as s:
        await s.execute(
            update(DersOturumu).where(DersOturumu.id == oturum_id).values(yoklama_ilk_kayit=simdi() - timedelta(minutes=dakika))
        )
        await s.commit()


async def test_kayit_oncesi_kilit_yok_ilk_kayit_kilit_zamani_verir(istemci, kurulum):
    ba, _, ot, o1, o2 = kurulum
    d = (await istemci.get(f"/api/oturumlar/{ot.id}", headers=ba)).json()
    assert d["kilit_zamani"] is None and d["kilitli"] is False
    r = await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o1, "geldi")), headers=ba)
    assert r.status_code == 200
    d = r.json()
    ilk = await ilk_kayit(ot.id)
    assert ilk is not None and d["kilitli"] is False and d["kilit_zamani"] is not None


async def test_antrenor_kilit_oncesi_degistirebilir_ve_ilk_kayit_kaymaz(istemci, kurulum):
    ba, _, ot, o1, o2 = kurulum
    url = f"/api/oturumlar/{ot.id}/yoklama"
    assert (await istemci.put(url, json=govde((o1, "geldi")), headers=ba)).status_code == 200
    ilk = await ilk_kayit(ot.id)
    # Aynı değerler: değişiklik yok. Sonra düzeltme ve yeni öğrenci ekleme: serbest.
    assert (await istemci.put(url, json=govde((o1, "geldi")), headers=ba)).status_code == 200
    assert (await istemci.put(url, json=govde((o1, "gelmedi"), (o2, "geldi")), headers=ba)).status_code == 200
    assert await ilk_kayit(ot.id) == ilk


async def test_antrenor_kilit_sonrasi_403_degisiklik_ekleme_ve_ayni_deger(istemci, kurulum):
    ba, _, ot, o1, o2 = kurulum
    url = f"/api/oturumlar/{ot.id}/yoklama"
    assert (await istemci.put(url, json=govde((o1, "geldi")), headers=ba)).status_code == 200
    await kilidi_gecir(ot.id)
    d = (await istemci.get(f"/api/oturumlar/{ot.id}", headers=ba)).json()
    assert d["kilitli"] is True
    for yuk in (govde((o1, "gelmedi")), govde((o1, "geldi"), (o2, "geldi"))):
        r = await istemci.put(url, json=yuk, headers=ba)
        assert r.status_code == 403 and r.json()["detail"] == MESAJ
        assert r.headers["X-Hata-Kodu"] == "yoklama_kilitli"
    # Değişmeyen yeniden gönderim zararsızdır.
    assert (await istemci.put(url, json=govde((o1, "geldi")), headers=ba)).status_code == 200
    async with SessionLocal() as s:
        assert len((await s.execute(select(Yoklama))).scalars().all()) == 1
        assert (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "yoklama_kilit_sonrasi_duzeltme"))).first() is None


async def test_yonetici_kilit_sonrasi_duzeltir_ve_denetim_yazilir(istemci, kurulum):
    ba, yon, ot, o1, o2 = kurulum
    url = f"/api/oturumlar/{ot.id}/yoklama"
    assert (await istemci.put(url, json=govde((o1, "geldi"), (o2, "geldi")), headers=ba)).status_code == 200
    await kilidi_gecir(ot.id)
    ilk = await ilk_kayit(ot.id)
    r = await istemci.put(url, json=govde((o1, "geldi"), (o2, "gelmedi")), headers=yon)
    assert r.status_code == 200 and r.json()["kilitli"] is True
    assert await ilk_kayit(ot.id) == ilk
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "yoklama_kilit_sonrasi_duzeltme"))).scalars().all()
    assert len(kayitlar) == 1
    assert kayitlar[0].hedef_id == str(ot.id)
    assert kayitlar[0].detay["degisen"] == [{"ogrenci_id": str(o2.id), "onceki": "geldi", "yeni": "gelmedi"}]
