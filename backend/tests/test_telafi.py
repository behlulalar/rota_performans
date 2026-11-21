"""Telafi: manuel düzeltme, kullanılabilir telafi, adaylar, planlama ve geri alma (HTTP üzerinden)."""
import asyncio
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    DenetimKaydi,
    DersHakkiHareketi,
    HareketTuru,
    Ogrenci,
    OgrenciDurum,
    OturumDurum,
    Rol,
    TelafiPlani,
)
from tests.test_yoklama import (
    BUGUN,
    antrenor_hesabi,
    govde,
    giris,
    grup_olustur,
    kaydet,
    ogrenci_olustur,
    oturum_olustur,
    uye_yap,
    yonetici,  # noqa: F401  (fixture)
)

YARIN = BUGUN + timedelta(days=1)
DUN = BUGUN - timedelta(days=1)


def gun(n):
    return BUGUN + timedelta(days=n)


async def duzelt(istemci, yonetici, ogrenci, sayac="telafi", miktar=1, neden="Deneme nedeni"):
    return await istemci.post(
        f"/api/ogrenciler/{ogrenci.id}/ders-hakki/duzeltme",
        json={"sayac": sayac, "miktar": miktar, "neden": neden},
        headers=yonetici,
    )


async def hakli_ogrenci(istemci, yonetici, telafi=1, ad="Ali", soyad="Yilmaz"):
    o = await ogrenci_olustur(ad, soyad)
    if telafi:
        assert (await duzelt(istemci, yonetici, o, "telafi", telafi)).status_code == 200
    return o


def plan_url(ot):
    return f"/api/oturumlar/{ot.id}/telafi"


async def planla(istemci, yonetici, ot, o):
    return await istemci.post(plan_url(ot), json={"ogrenci_id": str(o.id)}, headers=yonetici)


async def detay(istemci, yonetici, o):
    return (await istemci.get(f"/api/ogrenciler/{o.id}", headers=yonetici)).json()["ders_hakki"]


# ---------- manuel düzeltme ----------


async def test_duzeltme_arti_eksi_iki_sayac(istemci, yonetici):
    o = await ogrenci_olustur()
    assert (await duzelt(istemci, yonetici, o, "normal", 5)).json() == {"normal": 5, "telafi": 0}
    assert (await duzelt(istemci, yonetici, o, "telafi", 2)).json() == {"normal": 5, "telafi": 2}
    assert (await duzelt(istemci, yonetici, o, "normal", -7)).json() == {"normal": -2, "telafi": 2}
    assert (await duzelt(istemci, yonetici, o, "telafi", -50)).json() == {"normal": -2, "telafi": -48}
    async with SessionLocal() as s:
        satirlar = (await s.execute(select(DersHakkiHareketi).order_by(DersHakkiHareketi.id))).scalars().all()
    assert [(h.tur, h.sayac.value, h.miktar, h.neden) for h in satirlar][0] == (
        HareketTuru.manuel_duzeltme, "normal", 5, "Deneme nedeni"
    )
    assert all(h.olusturan_id is not None for h in satirlar) and len(satirlar) == 4


async def test_duzeltme_dogrulama(istemci, yonetici):
    o = await ogrenci_olustur()
    for miktar in (0, 51, -51):
        assert (await duzelt(istemci, yonetici, o, "normal", miktar)).status_code == 422
    for neden in ("", "  ", "ab", "  a ", "x" * 501):
        assert (await duzelt(istemci, yonetici, o, "normal", 1, neden)).status_code == 422
    assert (await duzelt(istemci, yonetici, o, "diger", 1)).status_code == 422
    assert (await duzelt(istemci, yonetici, o, "normal", 1, "  abc  ")).status_code == 200
    async with SessionLocal() as s:
        assert (await s.execute(select(DersHakkiHareketi.neden))).scalar_one() == "abc"
    assert (await duzelt(istemci, yonetici, o, "normal", 1, "x" * 500)).status_code == 200
    # Bulunamayan öğrenci.
    yok = await istemci.post(
        f"/api/ogrenciler/{uuid.uuid4()}/ders-hakki/duzeltme",
        json={"sayac": "normal", "miktar": 1, "neden": "abc"}, headers=yonetici,
    )
    assert yok.status_code == 404


async def test_duzeltme_denetimde_neden_yok_ve_pasifte_calisir(istemci, yonetici):
    o = await ogrenci_olustur()
    async with SessionLocal() as s:
        (await s.get(Ogrenci, o.id)).durum = OgrenciDurum.pasif
        await s.commit()
    assert (await duzelt(istemci, yonetici, o, "telafi", 3, "Gizli not metni")).status_code == 200
    async with SessionLocal() as s:
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ders_hakki_duzeltildi"))).scalar_one()
    assert k.detay == {"sayac": "telafi", "miktar": 3}
    assert "Gizli" not in str(k.detay) + str(k.hedef_id)


async def test_duzeltme_yetki(istemci, yonetici):
    o = await ogrenci_olustur()
    ba, _ = await antrenor_hesabi(istemci, "hoca@kulup.com", "Hoca")
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    url = f"/api/ogrenciler/{o.id}/ders-hakki/duzeltme"
    g = {"sayac": "normal", "miktar": 1, "neden": "abc"}
    assert (await istemci.post(url, json=g, headers=ba)).status_code == 403
    assert (await istemci.post(url, json=g, headers=veli)).status_code == 403
    assert (await istemci.post(url, json=g)).status_code == 401


# ---------- kullanılabilir telafi ----------


async def test_kullanilabilir_telafi_hesabi(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "hoca@kulup.com", "Hoca")
    g = await grup_olustur("GA", a)
    o = await hakli_ogrenci(istemci, yonetici, telafi=5)
    assert await detay(istemci, yonetici, o) == {"normal": 0, "telafi": 5, "kullanilabilir_telafi": 5}
    ileri, bugun_ot, gecmis = await oturum_olustur(g, gun(3)), await oturum_olustur(g, BUGUN), await oturum_olustur(g, DUN)
    await kaydet(
        TelafiPlani(oturum_id=ileri.id, ogrenci_id=o.id),
        TelafiPlani(oturum_id=bugun_ot.id, ogrenci_id=o.id),
        TelafiPlani(oturum_id=gecmis.id, ogrenci_id=o.id),  # geçmiş tarih düşülmez
    )
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 3
    # Bugünkü derse gelindi: yoklaması var, plan düşülmez; telafi bakiyesi 1 azalır.
    assert (
        await istemci.put(f"/api/oturumlar/{bugun_ot.id}/yoklama", json=govde((o, "geldi")), headers=yonetici)
    ).status_code == 200
    assert await detay(istemci, yonetici, o) == {"normal": 0, "telafi": 4, "kullanilabilir_telafi": 3}
    # Gelinmemiş telafi de düşülmez (telafi hakkı harcanmaz, plan artık açık değil).
    ileri2 = await oturum_olustur(g, gun(4))
    await kaydet(TelafiPlani(oturum_id=ileri2.id, ogrenci_id=o.id))
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 2
    ileri2_yok = await istemci.put(f"/api/oturumlar/{ileri2.id}/yoklama", json=govde((o, "gelmedi")), headers=yonetici)
    assert ileri2_yok.status_code == 422  # gelecek tarihli derse yoklama alınamaz
    # İptal edilen oturumdaki plan düşülmez.
    iptal = await oturum_olustur(g, gun(5), durum=OturumDurum.iptal)
    await kaydet(TelafiPlani(oturum_id=iptal.id, ogrenci_id=o.id))
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 2


async def test_gelinmemis_telafi_dusulmez(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "hoca@kulup.com", "Hoca")
    g = await grup_olustur("GA", a)
    o = await hakli_ogrenci(istemci, yonetici, telafi=2)
    bugun_ot = await oturum_olustur(g, BUGUN)
    await kaydet(TelafiPlani(oturum_id=bugun_ot.id, ogrenci_id=o.id))
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 1
    await istemci.put(f"/api/oturumlar/{bugun_ot.id}/yoklama", json=govde((o, "gelmedi")), headers=yonetici)
    assert await detay(istemci, yonetici, o) == {"normal": 0, "telafi": 2, "kullanilabilir_telafi": 2}


# ---------- adaylar ----------


async def test_adaylar_kurallar_ve_bos_yer(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "hoca@kulup.com", "Hoca")
    kendi = await grup_olustur("KENDI", a)
    diger = await grup_olustur("DIGER", a)
    pasif = await grup_olustur("PASIF", a, aktif=False)
    o = await hakli_ogrenci(istemci, yonetici)
    await uye_yap(o, kendi)
    kendi_ot = await oturum_olustur(kendi, gun(1))
    uygun = await oturum_olustur(diger, gun(2))
    uygun2 = await oturum_olustur(diger, gun(1))
    await oturum_olustur(diger, DUN)  # geçmiş
    await oturum_olustur(diger, gun(3), durum=OturumDurum.iptal)
    await oturum_olustur(pasif, gun(2))
    planli = await oturum_olustur(diger, gun(4))
    await kaydet(TelafiPlani(oturum_id=planli.id, ogrenci_id=o.id))
    # Dolu grup: kontenjan 10, 10 üye.
    dolu = await grup_olustur("DOLU", a)
    for i in range(10):
        await uye_yap(await ogrenci_olustur(f"D{i}", "Uye"), dolu)
    await oturum_olustur(dolu, gun(2))
    # Uygun oturuma: 3 üye + 1 telafi planı -> bos_yer 6.
    for i in range(3):
        await uye_yap(await ogrenci_olustur(f"U{i}", "Uye"), diger)
    await kaydet(TelafiPlani(oturum_id=uygun.id, ogrenci_id=(await ogrenci_olustur("T", "Plan")).id))
    yanit = await istemci.get(f"/api/ogrenciler/{o.id}/telafi-adaylari", headers=yonetici)
    assert yanit.status_code == 200
    liste = yanit.json()
    assert [(c["oturum"]["id"], c["bos_yer"]) for c in liste] == [(str(uygun2.id), 7), (str(uygun.id), 6)]
    assert str(kendi_ot.id) not in [c["oturum"]["id"] for c in liste]
    assert liste[0]["oturum"]["grup"] == {"id": str(diger.id), "ad": "DIGER"}
    assert {"id", "tarih", "baslangic", "bitis", "durum", "grup", "antrenor", "ogrenci_sayisi", "yoklama_alindi"} <= set(
        liste[0]["oturum"]
    )


async def test_adaylar_aralik_ve_31_gun_siniri(istemci, yonetici):
    g = await grup_olustur("DIGER")
    o = await hakli_ogrenci(istemci, yonetici)
    yakin, uzak = await oturum_olustur(g, gun(14)), await oturum_olustur(g, gun(15))
    # Varsayılan bugün..bugün+14.
    liste = (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-adaylari", headers=yonetici)).json()
    assert [c["oturum"]["id"] for c in liste] == [str(yakin.id)]
    url = f"/api/ogrenciler/{o.id}/telafi-adaylari?baslangic={BUGUN}&bitis={gun(30)}"
    liste = (await istemci.get(url, headers=yonetici)).json()
    assert [c["oturum"]["id"] for c in liste] == [str(yakin.id), str(uzak.id)]
    assert (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-adaylari?baslangic={BUGUN}&bitis={gun(31)}", headers=yonetici)).status_code == 422
    assert (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-adaylari?baslangic={gun(5)}&bitis={gun(4)}", headers=yonetici)).status_code == 422
    assert (await istemci.get(f"/api/ogrenciler/{uuid.uuid4()}/telafi-adaylari", headers=yonetici)).status_code == 404


async def test_adaylar_o_tarihte_uye_olmayan_ogrenci_gecmis_uyelik(istemci, yonetici):
    g = await grup_olustur("ESKI")
    o = await hakli_ogrenci(istemci, yonetici)
    await uye_yap(o, g, baslangic=gun(-30), bitis=gun(1))  # yarından sonra üye değil
    ot_uye, ot_degil = await oturum_olustur(g, gun(1)), await oturum_olustur(g, gun(2))
    liste = (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-adaylari", headers=yonetici)).json()
    assert [c["oturum"]["id"] for c in liste] == [str(ot_degil.id)]
    assert str(ot_uye.id) not in str(liste)


# ---------- planlama ----------


async def test_planlama_basarili_detay_takvim_ve_denetim(istemci, yonetici):
    g = await grup_olustur("DIGER")
    uye = await ogrenci_olustur("Uye", "Biri")
    await uye_yap(uye, g)
    ot = await oturum_olustur(g, gun(2))
    o = await hakli_ogrenci(istemci, yonetici, telafi=1, ad="Zeynep", soyad="Telafi")
    takvim = f"/api/takvim?baslangic={gun(2)}&bitis={gun(2)}"
    assert (await istemci.get(takvim, headers=yonetici)).json()[0]["ogrenci_sayisi"] == 1
    yanit = await planla(istemci, yonetici, ot, o)
    assert yanit.status_code == 200
    d = yanit.json()
    assert d["ogrenci_sayisi"] == 2
    assert {x["ad"]: x["telafi_mi"] for x in d["ogrenciler"]} == {"Uye": False, "Zeynep": True}
    assert (await istemci.get(f"/api/oturumlar/{ot.id}", headers=yonetici)).json()["ogrenciler"] == d["ogrenciler"]
    assert (await istemci.get(takvim, headers=yonetici)).json()[0]["ogrenci_sayisi"] == 2
    assert await detay(istemci, yonetici, o) == {"normal": 0, "telafi": 1, "kullanilabilir_telafi": 0}
    async with SessionLocal() as s:
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "telafi_planlandi"))).scalar_one()
        plan = (await s.execute(select(TelafiPlani))).scalar_one()
    assert k.hedef_id == str(ot.id) and plan.olusturan_id is not None
    # Planlı öğrenci aday listesinde yok ve planlar ucunda görünür.
    planlar = (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-planlari", headers=yonetici)).json()
    assert planlar == [{
        "oturum_id": str(ot.id), "tarih": str(gun(2)), "baslangic": "00:00:00", "bitis": "01:30:00",
        "grup": {"id": str(g.id), "ad": "DIGER"}, "yoklama": None, "iptal_edilebilir": True,
    }]


async def test_planlama_kurallari(istemci, yonetici):
    g = await grup_olustur("DIGER")
    o = await hakli_ogrenci(istemci, yonetici, telafi=1)
    ot = await oturum_olustur(g, gun(2))

    async def hata(oturum, ogrenci, kod, mesaj):
        y = await planla(istemci, yonetici, oturum, ogrenci)
        assert (y.status_code, y.json()["detail"]) == (kod, mesaj)

    # 404'ler
    assert (await istemci.post(plan_url(ot), json={"ogrenci_id": str(uuid.uuid4())}, headers=yonetici)).status_code == 404
    assert (
        await istemci.post(f"/api/oturumlar/{uuid.uuid4()}/telafi", json={"ogrenci_id": str(o.id)}, headers=yonetici)
    ).status_code == 404
    # Geçmiş ders, iptal
    await hata(await oturum_olustur(g, DUN), o, 422, "Geçmiş derse telafi planlanamaz")
    iptal = await oturum_olustur(g, gun(3), durum=OturumDurum.iptal)
    y = await planla(istemci, yonetici, iptal, o)
    assert y.status_code == 422
    # Üye
    uye = await hakli_ogrenci(istemci, yonetici, telafi=1, ad="Uye", soyad="Grup")
    await uye_yap(uye, g)
    await hata(ot, uye, 422, "Öğrenci bu grubun üyesi, telafi gerekmez")
    # Hak yok
    hak_yok = await ogrenci_olustur("Hak", "Yok")
    await hata(ot, hak_yok, 422, "Kullanılabilir telafi hakkı yok")
    # Pasif
    async with SessionLocal() as s:
        (await s.get(Ogrenci, o.id)).durum = OgrenciDurum.pasif
        await s.commit()
    await hata(ot, o, 422, "Pasif öğrenci için telafi planlanamaz")
    async with SessionLocal() as s:
        (await s.get(Ogrenci, o.id)).durum = OgrenciDurum.aktif
        await s.commit()
    # Başarılı ve tekrar
    assert (await planla(istemci, yonetici, ot, o)).status_code == 200
    await hata(ot, o, 409, "Öğrenci bu derse zaten telafi için eklendi")
    # Hak negatif/0 (kullanılabilir hesaba plan düşülür)
    ot2 = await oturum_olustur(g, gun(4))
    await hata(ot2, o, 422, "Kullanılabilir telafi hakkı yok")


async def test_planlama_dolu_ders(istemci, yonetici):
    g = await grup_olustur("DIGER")
    for i in range(10):
        await uye_yap(await ogrenci_olustur(f"D{i}", "Uye"), g)
    ot = await oturum_olustur(g, gun(2))
    o = await hakli_ogrenci(istemci, yonetici)
    y = await planla(istemci, yonetici, ot, o)
    assert (y.status_code, y.json()["detail"]) == (409, "Bu derste boş yer yok")
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 1


async def test_son_hak_esanli_istekte_bir_kez_kullanilir(istemci, yonetici):
    g = await grup_olustur("DIGER")
    o = await hakli_ogrenci(istemci, yonetici, telafi=1)
    ot1, ot2 = await oturum_olustur(g, gun(2)), await oturum_olustur(g, gun(3))
    y1, y2 = await asyncio.gather(planla(istemci, yonetici, ot1, o), planla(istemci, yonetici, ot2, o))
    assert sorted([y1.status_code, y2.status_code]) == [200, 422]
    async with SessionLocal() as s:
        assert len((await s.execute(select(TelafiPlani))).scalars().all()) == 1
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 0


async def test_kontenjan_son_yer_esanli_iki_ogrenci(istemci, yonetici):
    g = await grup_olustur("DIGER")
    for i in range(9):
        await uye_yap(await ogrenci_olustur(f"D{i}", "Uye"), g)
    ot = await oturum_olustur(g, gun(2))
    a, b = await hakli_ogrenci(istemci, yonetici, ad="A", soyad="A"), await hakli_ogrenci(istemci, yonetici, ad="B", soyad="B")
    y1, y2 = await asyncio.gather(planla(istemci, yonetici, ot, a), planla(istemci, yonetici, ot, b))
    assert sorted([y1.status_code, y2.status_code]) == [200, 409]


async def test_planli_ogrenci_gelince_telafi_duser_ve_hesap_tutarli(istemci, yonetici):
    ba, a = await antrenor_hesabi(istemci, "hoca@kulup.com", "Hoca")
    g = await grup_olustur("DIGER", a)
    o = await hakli_ogrenci(istemci, yonetici, telafi=2)
    ot = await oturum_olustur(g, BUGUN)
    assert (await planla(istemci, yonetici, ot, o)).status_code == 200
    assert await detay(istemci, yonetici, o) == {"normal": 0, "telafi": 2, "kullanilabilir_telafi": 1}
    yanit = await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o, "geldi")), headers=ba)
    assert yanit.status_code == 200 and yanit.json()["ogrenciler"][0]["bakiye"] == {"normal": 0, "telafi": 1}
    assert await detay(istemci, yonetici, o) == {"normal": 0, "telafi": 1, "kullanilabilir_telafi": 1}
    planlar = (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-planlari", headers=yonetici)).json()
    assert planlar[0]["yoklama"] == "geldi"


async def test_telafi_planlari_tarih_azalan(istemci, yonetici):
    g = await grup_olustur("DIGER")
    o = await ogrenci_olustur()
    ots = [await oturum_olustur(g, gun(n)) for n in (-2, 5, 1)]
    await kaydet(*[TelafiPlani(oturum_id=x.id, ogrenci_id=o.id) for x in ots])
    planlar = (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-planlari", headers=yonetici)).json()
    assert [p["tarih"] for p in planlar] == [str(gun(5)), str(gun(1)), str(gun(-2))]
    assert (await istemci.get(f"/api/ogrenciler/{uuid.uuid4()}/telafi-planlari", headers=yonetici)).status_code == 404


# ---------- geri alma ----------


async def test_geri_alma(istemci, yonetici):
    g = await grup_olustur("DIGER")
    o = await hakli_ogrenci(istemci, yonetici)
    ot = await oturum_olustur(g, gun(2))
    assert (await planla(istemci, yonetici, ot, o)).status_code == 200
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 0
    yanit = await istemci.delete(f"{plan_url(ot)}/{o.id}", headers=yonetici)
    assert yanit.status_code == 200 and yanit.json()["ogrenciler"] == [] and yanit.json()["ogrenci_sayisi"] == 0
    assert (await detay(istemci, yonetici, o))["kullanilabilir_telafi"] == 1
    async with SessionLocal() as s:
        assert (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "telafi_iptal_edildi"))).scalar_one()
    assert (await istemci.delete(f"{plan_url(ot)}/{o.id}", headers=yonetici)).status_code == 404


async def test_yoklamali_telafi_geri_alinamaz(istemci, yonetici):
    g = await grup_olustur("DIGER")
    o = await hakli_ogrenci(istemci, yonetici)
    ot = await oturum_olustur(g, BUGUN)
    assert (await planla(istemci, yonetici, ot, o)).status_code == 200
    await istemci.put(f"/api/oturumlar/{ot.id}/yoklama", json=govde((o, "gelmedi")), headers=yonetici)
    y = await istemci.delete(f"{plan_url(ot)}/{o.id}", headers=yonetici)
    assert (y.status_code, y.json()["detail"]) == (409, "Yoklaması alınmış telafi geri alınamaz")


# ---------- yetki ----------


async def test_telafi_uclari_yetki(istemci, yonetici):
    g = await grup_olustur("DIGER")
    o = await hakli_ogrenci(istemci, yonetici)
    ot = await oturum_olustur(g, gun(2))
    ba, _ = await antrenor_hesabi(istemci, "hoca@kulup.com", "Hoca")
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    uclar = [
        ("get", f"/api/ogrenciler/{o.id}/telafi-adaylari", None),
        ("get", f"/api/ogrenciler/{o.id}/telafi-planlari", None),
        ("post", plan_url(ot), {"ogrenci_id": str(o.id)}),
        ("delete", f"{plan_url(ot)}/{o.id}", None),
    ]
    for yontem, url, json in uclar:
        for baslik, kod in ((ba, 403), (veli, 403), (None, 401)):
            kw = {"headers": baslik} if baslik else {}
            if json is not None:
                kw["json"] = json
            yanit = await getattr(istemci, yontem)(url, **kw)
            assert yanit.status_code == kod, (yontem, url, kod)
