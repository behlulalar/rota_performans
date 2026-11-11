import asyncio
import uuid
from datetime import date, time, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DenetimKaydi, Ogrenci, Rol
from app.models.program import DersOturumu, OgrenciGrup
from app.models.yoklama import Yoklama, YoklamaDurum
from app.oturumlar import bugun
from tests.conftest import SIFRE, kullanici_olustur

TC_LISTESI = ["10000000146", "10000001068"]


async def giris(istemci, eposta, rol):
    await kullanici_olustur(eposta, rol)
    yanit = await istemci.post("/api/auth/login", json={"giris": eposta, "sifre": SIFRE})
    return {"Authorization": f"Bearer {yanit.json()['access_token']}"}


@pytest.fixture
async def yonetici(istemci):
    return await giris(istemci, "yonetici@kulup.com", Rol.admin)


async def ogrenci_olustur(istemci, baslik, ad="Deneme", soyad="Öğrenci"):
    from datetime import date

    async with SessionLocal() as s:
        o = Ogrenci(ad=ad, soyad=soyad, dogum_tarihi=date(2015, 5, 10))
        s.add(o)
        await s.commit()
        return str(o.id)


async def antrenor_olustur(istemci, baslik, giris_="0532 000 00 01", ad="Hoca Bir"):
    yanit = await istemci.post(
        "/api/antrenorler", json={"ad_soyad": ad, "telefon": giris_}, headers=baslik
    )
    assert yanit.status_code == 201, yanit.text
    return yanit.json()["antrenor"]


async def grup_olustur(istemci, baslik, **ek):
    govde = {"ad": "U10", "kontenjan": 5, "program": [{"gun": 1, "baslangic": "17:00", "bitis": "18:30"}]}
    govde.update(ek)
    yanit = await istemci.post("/api/gruplar", json=govde, headers=baslik)
    assert yanit.status_code == 201, yanit.text
    return yanit.json()


async def test_grup_olusturma_ve_program_sirasi(istemci, yonetici):
    a = await antrenor_olustur(istemci, yonetici)
    g = await grup_olustur(
        istemci,
        yonetici,
        antrenor_id=a["id"],
        program=[
            {"gun": 3, "baslangic": "10:00", "bitis": "11:30"},
            {"gun": 1, "baslangic": "18:00", "bitis": "19:00"},
            {"gun": 1, "baslangic": "09:00", "bitis": "10:00"},
        ],
    )
    assert g["antrenor"] == {"id": a["id"], "ad_soyad": "Hoca Bir"}
    assert g["ogrenci_sayisi"] == 0 and g["ogrenciler"] == [] and g["aktif"] is True
    assert [(s["gun"], s["baslangic"]) for s in g["program"]] == [(1, "09:00"), (1, "18:00"), (3, "10:00")]
    assert all(s["id"] for s in g["program"])
    liste = (await istemci.get("/api/gruplar", headers=yonetici)).json()
    assert liste[0]["antrenor"]["id"] == a["id"]
    assert "ogrenciler" not in liste[0]
    # Antrenörün aktif grup sayısı
    antrenorler = (await istemci.get("/api/antrenorler", headers=yonetici)).json()
    assert antrenorler[0]["grup_sayisi"] == 1


@pytest.mark.parametrize(
    "program",
    [
        [{"gun": 0, "baslangic": "10:00", "bitis": "11:00"}],
        [{"gun": 8, "baslangic": "10:00", "bitis": "11:00"}],
        [{"gun": 1, "baslangic": "11:00", "bitis": "10:00"}],
        [{"gun": 1, "baslangic": "10:00", "bitis": "10:00"}],
        [{"gun": 1, "baslangic": "25:00", "bitis": "26:00"}],
        [{"gun": 1, "baslangic": "9:00", "bitis": "10:00"}],
        [
            {"gun": 1, "baslangic": "10:00", "bitis": "11:00"},
            {"gun": 1, "baslangic": "10:00", "bitis": "12:00"},
        ],
    ],
)
async def test_gecersiz_program_422(istemci, yonetici, program):
    yanit = await istemci.post(
        "/api/gruplar", json={"ad": "X", "kontenjan": 3, "program": program}, headers=yonetici
    )
    assert yanit.status_code == 422


async def test_gecersiz_grup_alanlari(istemci, yonetici):
    assert (
        await istemci.post("/api/gruplar", json={"ad": "X", "kontenjan": 0, "program": []}, headers=yonetici)
    ).status_code == 422
    assert (
        await istemci.post("/api/gruplar", json={"ad": "  ", "kontenjan": 3, "program": []}, headers=yonetici)
    ).status_code == 422
    # Olmayan antrenör
    yanit = await istemci.post(
        "/api/gruplar",
        json={"ad": "X", "kontenjan": 3, "program": [], "antrenor_id": str(uuid.uuid4())},
        headers=yonetici,
    )
    assert yanit.status_code == 422
    # Pasif antrenör
    a = await antrenor_olustur(istemci, yonetici)
    await istemci.patch(f"/api/antrenorler/{a['id']}", json={"aktif": False}, headers=yonetici)
    yanit = await istemci.post(
        "/api/gruplar", json={"ad": "X", "kontenjan": 3, "program": [], "antrenor_id": a["id"]}, headers=yonetici
    )
    assert yanit.status_code == 422


async def test_ogrenci_ekleme_liste_sayisi_ve_detay(istemci, yonetici):
    g = await grup_olustur(istemci, yonetici)
    o1 = await ogrenci_olustur(istemci, yonetici, "Ayşe", "Yılmaz")
    o2 = await ogrenci_olustur(istemci, yonetici, "Can", "Altın")
    for o in (o1, o2):
        yanit = await istemci.post(f"/api/gruplar/{g['id']}/ogrenciler", json={"ogrenci_id": o}, headers=yonetici)
        assert yanit.status_code == 200, yanit.text
    d = (await istemci.get(f"/api/gruplar/{g['id']}", headers=yonetici)).json()
    assert d["ogrenci_sayisi"] == 2
    assert [o["soyad"] for o in d["ogrenciler"]] == ["Altın", "Yılmaz"]
    assert set(d["ogrenciler"][0]) == {"id", "ad", "soyad", "yas", "foto_var", "katilim_baslangic"}
    assert d["ogrenciler"][0]["foto_var"] is False
    liste = (await istemci.get("/api/gruplar", headers=yonetici)).json()
    assert liste[0]["ogrenci_sayisi"] == 2
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi.islem))).scalars().all()
    assert kayitlar.count("grup_ogrenci_eklendi") == 2


async def test_ogrenci_detayinda_gruplar(istemci, yonetici):
    g1 = await grup_olustur(istemci, yonetici, ad="A grubu")
    g2 = await grup_olustur(istemci, yonetici, ad="B grubu")
    o = await ogrenci_olustur(istemci, yonetici)
    for g in (g1, g2):
        await istemci.post(f"/api/gruplar/{g['id']}/ogrenciler", json={"ogrenci_id": o}, headers=yonetici)
    await istemci.delete(f"/api/gruplar/{g1['id']}/ogrenciler/{o}", headers=yonetici)
    d = (await istemci.get(f"/api/ogrenciler/{o}", headers=yonetici)).json()
    assert d["gruplar"] == [{"id": g2["id"], "ad": "B Grubu"}]


async def test_kontenjan_dolu_ve_tekrar(istemci, yonetici):
    g = await grup_olustur(istemci, yonetici, kontenjan=1)
    o1 = await ogrenci_olustur(istemci, yonetici, "A", "A")
    o2 = await ogrenci_olustur(istemci, yonetici, "B", "B")
    url = f"/api/gruplar/{g['id']}/ogrenciler"
    assert (await istemci.post(url, json={"ogrenci_id": o1}, headers=yonetici)).status_code == 200
    yanit = await istemci.post(url, json={"ogrenci_id": o1}, headers=yonetici)
    assert yanit.status_code == 409 and yanit.json()["detail"] == "Öğrenci zaten bu grupta"
    yanit = await istemci.post(url, json={"ogrenci_id": o2}, headers=yonetici)
    assert yanit.status_code == 409 and yanit.json()["detail"] == "Grup kontenjanı dolu"


async def test_ekleme_hatalari(istemci, yonetici):
    g = await grup_olustur(istemci, yonetici)
    url = f"/api/gruplar/{g['id']}/ogrenciler"
    assert (await istemci.post(url, json={"ogrenci_id": str(uuid.uuid4())}, headers=yonetici)).status_code == 404
    assert (
        await istemci.post(f"/api/gruplar/{uuid.uuid4()}/ogrenciler", json={"ogrenci_id": str(uuid.uuid4())}, headers=yonetici)
    ).status_code == 404
    o = await ogrenci_olustur(istemci, yonetici)
    await istemci.post(f"/api/ogrenciler/{o}/pasife-al", headers=yonetici)
    yanit = await istemci.post(url, json={"ogrenci_id": o}, headers=yonetici)
    assert yanit.status_code == 422 and yanit.json()["detail"] == "Pasif öğrenci gruba eklenemez"
    # Pasif grup
    o2 = await ogrenci_olustur(istemci, yonetici, "B", "B")
    await istemci.patch(f"/api/gruplar/{g['id']}", json={"aktif": False}, headers=yonetici)
    assert (await istemci.post(url, json={"ogrenci_id": o2}, headers=yonetici)).status_code == 422


async def test_cikarma_ve_yeniden_ekleme(istemci, yonetici):
    g = await grup_olustur(istemci, yonetici, kontenjan=1)
    o = await ogrenci_olustur(istemci, yonetici)
    url = f"/api/gruplar/{g['id']}/ogrenciler"
    await istemci.post(url, json={"ogrenci_id": o}, headers=yonetici)
    yanit = await istemci.delete(f"{url}/{o}", headers=yonetici)
    assert yanit.status_code == 200
    assert yanit.json()["ogrenci_sayisi"] == 0 and yanit.json()["ogrenciler"] == []
    # Silinmez, bitişi işlenir.
    async with SessionLocal() as s:
        uyelikler = (await s.execute(select(OgrenciGrup))).scalars().all()
    assert len(uyelikler) == 1 and uyelikler[0].bitis is not None
    assert (await istemci.delete(f"{url}/{o}", headers=yonetici)).status_code == 404
    assert (await istemci.post(url, json={"ogrenci_id": o}, headers=yonetici)).status_code == 200
    async with SessionLocal() as s:
        assert len((await s.execute(select(OgrenciGrup))).scalars().all()) == 2


async def test_kontenjan_dusurme(istemci, yonetici):
    g = await grup_olustur(istemci, yonetici, kontenjan=3)
    for i in range(2):
        o = await ogrenci_olustur(istemci, yonetici, f"A{i}", f"S{i}")
        await istemci.post(f"/api/gruplar/{g['id']}/ogrenciler", json={"ogrenci_id": o}, headers=yonetici)
    yanit = await istemci.patch(f"/api/gruplar/{g['id']}", json={"kontenjan": 1}, headers=yonetici)
    assert yanit.status_code == 409
    assert yanit.json()["detail"] == "Kontenjan mevcut öğrenci sayısından az olamaz"
    yanit = await istemci.patch(f"/api/gruplar/{g['id']}", json={"kontenjan": 2, "ad": "Yeni"}, headers=yonetici)
    assert yanit.status_code == 200 and yanit.json()["kontenjan"] == 2 and yanit.json()["ad"] == "Yeni"


async def test_antrenor_atama_ve_kaldirma(istemci, yonetici):
    a = await antrenor_olustur(istemci, yonetici)
    g = await grup_olustur(istemci, yonetici)
    assert g["antrenor"] is None
    yanit = await istemci.patch(f"/api/gruplar/{g['id']}", json={"antrenor_id": a["id"]}, headers=yonetici)
    assert yanit.json()["antrenor"]["id"] == a["id"]
    # Alan gönderilmezse antrenör korunur.
    yanit = await istemci.patch(f"/api/gruplar/{g['id']}", json={"ad": "Z"}, headers=yonetici)
    assert yanit.json()["antrenor"]["id"] == a["id"]
    yanit = await istemci.patch(f"/api/gruplar/{g['id']}", json={"antrenor_id": None}, headers=yonetici)
    assert yanit.json()["antrenor"] is None
    yanit = await istemci.patch(f"/api/gruplar/{g['id']}", json={"antrenor_id": str(uuid.uuid4())}, headers=yonetici)
    assert yanit.status_code == 422


async def test_program_degistirme(istemci, yonetici):
    g = await grup_olustur(
        istemci,
        yonetici,
        program=[
            {"gun": 1, "baslangic": "17:00", "bitis": "18:30"},
            {"gun": 2, "baslangic": "17:00", "bitis": "18:30"},
        ],
    )
    s1, s2 = g["program"]
    yeni = [
        {"id": s1["id"], "gun": 1, "baslangic": "17:00", "bitis": "19:00"},
        {"gun": 5, "baslangic": "09:00", "bitis": "10:30"},
    ]
    yanit = await istemci.put(f"/api/gruplar/{g['id']}/program", json=yeni, headers=yonetici)
    assert yanit.status_code == 200, yanit.text
    p = yanit.json()["program"]
    assert [(x["gun"], x["bitis"]) for x in p] == [(1, "19:00"), (5, "10:30")]
    assert p[0]["id"] == s1["id"]
    assert s2["id"] not in {x["id"] for x in p}
    # Başka gruba ait/olmayan id
    yanit = await istemci.put(
        f"/api/gruplar/{g['id']}/program",
        json=[{"id": s2["id"], "gun": 1, "baslangic": "10:00", "bitis": "11:00"}],
        headers=yonetici,
    )
    assert yanit.status_code == 422
    # Boş liste programı temizler
    yanit = await istemci.put(f"/api/gruplar/{g['id']}/program", json=[], headers=yonetici)
    assert yanit.status_code == 200 and yanit.json()["program"] == []
    # Tekrar eden slot
    yanit = await istemci.put(
        f"/api/gruplar/{g['id']}/program",
        json=[
            {"gun": 1, "baslangic": "10:00", "bitis": "11:00"},
            {"gun": 1, "baslangic": "10:00", "bitis": "11:30"},
        ],
        headers=yonetici,
    )
    assert yanit.status_code == 422


async def test_program_saati_degisince_ileri_dersler_yeniden_uretilir(istemci, yonetici):
    gun = bugun() + timedelta(days=1)
    g = await grup_olustur(
        istemci, yonetici, program=[{"gun": gun.isoweekday(), "baslangic": "17:00", "bitis": "18:30"}]
    )
    slot = g["program"][0]
    gid = uuid.UUID(g["id"])
    async with SessionLocal() as s:
        # Üretici çalışmış gibi: ileri tarihli planlı iki ders (biri yoklamalı) ve geçmiş bir ders.
        s.add_all([
            DersOturumu(grup_id=gid, grup_programi_id=uuid.UUID(slot["id"]), tarih=gun, baslangic=time(17), bitis=time(18, 30)),
            DersOturumu(grup_id=gid, grup_programi_id=uuid.UUID(slot["id"]), tarih=gun + timedelta(days=7), baslangic=time(17), bitis=time(18, 30)),
            DersOturumu(grup_id=gid, grup_programi_id=uuid.UUID(slot["id"]), tarih=bugun() - timedelta(days=7), baslangic=time(17), bitis=time(18, 30)),
        ])
        await s.commit()
    async with SessionLocal() as s:
        korunan = (
            await s.execute(select(DersOturumu).where(DersOturumu.grup_id == gid, DersOturumu.tarih == gun + timedelta(days=7)))
        ).scalar_one()
        ogr = Ogrenci(ad="Ali", soyad="Veli", dogum_tarihi=date(2015, 1, 1))
        s.add(ogr)
        await s.flush()
        s.add(Yoklama(oturum_id=korunan.id, ogrenci_id=ogr.id, durum=YoklamaDurum.geldi, telafi_mi=False, surum=0, hareket_islendi=True))
        await s.commit()

    yanit = await istemci.put(
        f"/api/gruplar/{g['id']}/program",
        json=[{"id": slot["id"], "gun": gun.isoweekday(), "baslangic": "19:00", "bitis": "20:30"}],
        headers=yonetici,
    )
    assert yanit.status_code == 200, yanit.text
    async with SessionLocal() as s:
        satirlar = (await s.execute(select(DersOturumu).where(DersOturumu.grup_id == gid))).scalars().all()
    saatler = sorted((o.tarih, o.baslangic) for o in satirlar)
    # Geçmiş ders ve yoklaması alınmış ders eski saatte kalır; diğer ileri dersler yeni saatte üretilir, çift ders oluşmaz.
    assert (bugun() - timedelta(days=7), time(17)) in saatler
    assert (gun + timedelta(days=7), time(17)) in saatler
    assert (gun, time(19)) in saatler and (gun, time(17)) not in saatler
    assert len({(o.tarih, o.baslangic) for o in satirlar}) == len(satirlar)


async def test_ogrenci_pasife_alininca_uyelikler_kapanir(istemci, yonetici):
    g1 = await grup_olustur(istemci, yonetici, ad="A")
    g2 = await grup_olustur(istemci, yonetici, ad="B")
    o = await ogrenci_olustur(istemci, yonetici)
    for g in (g1, g2):
        await istemci.post(f"/api/gruplar/{g['id']}/ogrenciler", json={"ogrenci_id": o}, headers=yonetici)
    yanit = await istemci.post(f"/api/ogrenciler/{o}/pasife-al", headers=yonetici)
    assert yanit.status_code == 200 and yanit.json()["gruplar"] == []
    for g in (g1, g2):
        d = (await istemci.get(f"/api/gruplar/{g['id']}", headers=yonetici)).json()
        assert d["ogrenci_sayisi"] == 0
    async with SessionLocal() as s:
        uyelikler = (await s.execute(select(OgrenciGrup))).scalars().all()
    assert len(uyelikler) == 2 and all(u.bitis is not None for u in uyelikler)


async def test_eszamanli_ekleme_kontenjani_asmaz(istemci, yonetici):
    g = await grup_olustur(istemci, yonetici, kontenjan=1)
    o1 = await ogrenci_olustur(istemci, yonetici, "A", "A")
    o2 = await ogrenci_olustur(istemci, yonetici, "B", "B")
    url = f"/api/gruplar/{g['id']}/ogrenciler"
    yanitlar = await asyncio.gather(
        istemci.post(url, json={"ogrenci_id": o1}, headers=yonetici),
        istemci.post(url, json={"ogrenci_id": o2}, headers=yonetici),
    )
    assert sorted(y.status_code for y in yanitlar) == [200, 409]
    d = (await istemci.get(f"/api/gruplar/{g['id']}", headers=yonetici)).json()
    assert d["ogrenci_sayisi"] == 1


async def test_yetki(istemci, yonetici):
    antrenor = await giris(istemci, "hoca@kulup.com", Rol.antrenor)
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    sahte = str(uuid.uuid4())
    uclar = [
        ("get", "/api/gruplar", None),
        ("post", "/api/gruplar", {"ad": "X", "kontenjan": 3, "program": []}),
        ("get", f"/api/gruplar/{sahte}", None),
        ("patch", f"/api/gruplar/{sahte}", {"ad": "Y"}),
        ("put", f"/api/gruplar/{sahte}/program", []),
        ("post", f"/api/gruplar/{sahte}/ogrenciler", {"ogrenci_id": sahte}),
        ("delete", f"/api/gruplar/{sahte}/ogrenciler/{sahte}", None),
    ]
    for yontem, yol, govde in uclar:
        for baslik in (antrenor, veli):
            assert (await istemci.request(yontem, yol, json=govde, headers=baslik)).status_code == 403, (yontem, yol)
        assert (await istemci.request(yontem, yol, json=govde)).status_code == 401, (yontem, yol)


async def test_grup_bulunamadi_404(istemci, yonetici):
    sahte = str(uuid.uuid4())
    assert (await istemci.get(f"/api/gruplar/{sahte}", headers=yonetici)).status_code == 404
    assert (await istemci.patch(f"/api/gruplar/{sahte}", json={"ad": "Y"}, headers=yonetici)).status_code == 404
