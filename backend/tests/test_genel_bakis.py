from datetime import date, time, timedelta
from decimal import Decimal

from app.db import SessionLocal
from app.models import (
    Antrenor,
    Grup,
    IletisimKisisi,
    IletisimRolu,
    Kullanici,
    Ogrenci,
    OgrenciDurum,
    OgrenciPaketi,
    OgrenciPaketiDurum,
    Paket,
    PaketTuru,
    Rol,
)
from app.models.program import GrupProgrami, OgrenciGrup
from tests.conftest import SIFRE, kullanici_olustur


async def giris(istemci, eposta, rol):
    await kullanici_olustur(eposta, rol)
    yanit = await istemci.post("/api/auth/login", json={"giris": eposta, "sifre": SIFRE})
    return {"Authorization": f"Bearer {yanit.json()['access_token']}"}


def ogrenci(ad, **ek):
    return Ogrenci(ad=ad, soyad="Test", dogum_tarihi=date(2015, 1, 1), **ek)


async def test_bos_veritabani(istemci):
    baslik = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    yanit = await istemci.get("/api/genel-bakis", headers=baslik)
    assert yanit.status_code == 200
    assert yanit.json() == {
        "ogrenci": {"aktif": 0, "pasif": 0, "bu_ay_kayit": 0},
        "hesapsiz_aktif_ogrenci": 0,
        "grupsuz_aktif_ogrenci": 0,
        "gruplar": {"aktif_grup": 0, "toplam_kontenjan": 0, "dolu": 0, "doluluk_listesi": []},
        "antrenor": {"aktif": 0},
        "bekleyen_odeme": {"adet": 0, "toplam_tutar": "0.00"},
        "son_kayitlar": [],
    }


async def test_sayaclar(istemci):
    baslik = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    bugun = date.today()
    eski = bugun.replace(day=1) - timedelta(days=1)
    async with SessionLocal() as s:
        veli = Kullanici(rol=Rol.veli, giris="veli@kulup.com", sifre_ozeti="x", aktif=True)
        s.add(veli)
        await s.flush()
        # a: hesaplı, grupta, bu ay kayıtlı. b: hesapsız, grupsuz, eski kayıt.
        a = ogrenci("A", kayit_tarihi=bugun, foto_anahtar="x.jpg")
        b = ogrenci("B", kayit_tarihi=eski)
        # c: aktif, grup üyeliği bitmiş, birincil kişisi yok.
        c = ogrenci("C", kayit_tarihi=eski)
        pasif = ogrenci("Pasif", durum=OgrenciDurum.pasif, kayit_tarihi=bugun)
        sentetik = ogrenci("Sentetik", sentetik=True, kayit_tarihi=bugun)
        s.add_all([a, b, c, pasif, sentetik])
        await s.flush()
        s.add_all(
            [
                IletisimKisisi(ogrenci_id=a.id, rol=IletisimRolu.anne, ad_soyad="Anne", telefon="1", birincil=True, kullanici_id=veli.id),
                IletisimKisisi(ogrenci_id=b.id, rol=IletisimRolu.anne, ad_soyad="Anne", telefon="2", birincil=True),
            ]
        )
        aktif_grup = Grup(ad="U10", kontenjan=4)
        dolu_grup = Grup(ad="U12", kontenjan=2)
        pasif_grup = Grup(ad="Eski", kontenjan=9, aktif=False)
        s.add_all([aktif_grup, dolu_grup, pasif_grup, Antrenor(ad_soyad="H1"), Antrenor(ad_soyad="H2", aktif=False)])
        await s.flush()
        # Program bilerek sırasız eklenir; yanıt gün + saat sıralı olmalı.
        s.add_all(
            [
                GrupProgrami(grup_id=aktif_grup.id, gun=5, baslangic=time(17, 30), bitis=time(19, 0)),
                GrupProgrami(grup_id=aktif_grup.id, gun=3, baslangic=time(17, 30), bitis=time(19, 0)),
                GrupProgrami(grup_id=aktif_grup.id, gun=1, baslangic=time(7, 0), bitis=time(8, 30)),
                GrupProgrami(grup_id=pasif_grup.id, gun=2, baslangic=time(10, 0), bitis=time(11, 0)),
            ]
        )
        s.add_all(
            [
                OgrenciGrup(ogrenci_id=a.id, grup_id=aktif_grup.id),
                OgrenciGrup(ogrenci_id=a.id, grup_id=dolu_grup.id),
                OgrenciGrup(ogrenci_id=sentetik.id, grup_id=dolu_grup.id),
                OgrenciGrup(ogrenci_id=c.id, grup_id=aktif_grup.id, baslangic=eski, bitis=eski),
                OgrenciGrup(ogrenci_id=b.id, grup_id=pasif_grup.id),
            ]
        )
        paket = Paket(ad="Aylık", tur=PaketTuru.aylik, ders_sayisi=8, sure_ay=1, varsayilan_fiyat=Decimal("1000"))
        s.add(paket)
        await s.flush()

        def op(o, fiyat, durum):
            return OgrenciPaketi(
                ogrenci_id=o.id, paket_id=paket.id, ders_sayisi=8, liste_fiyati=fiyat, uygulanan_fiyat=fiyat, durum=durum
            )

        s.add_all(
            [
                op(a, Decimal("1000.50"), OgrenciPaketiDurum.odeme_bekliyor),
                op(b, Decimal("234.00"), OgrenciPaketiDurum.odeme_bekliyor),
                op(c, Decimal("500"), OgrenciPaketiDurum.odendi),
                op(sentetik, Decimal("999"), OgrenciPaketiDurum.odeme_bekliyor),
            ]
        )
        await s.commit()

    j = (await istemci.get("/api/genel-bakis", headers=baslik)).json()
    assert j["ogrenci"] == {"aktif": 3, "pasif": 1, "bu_ay_kayit": 1}
    assert j["hesapsiz_aktif_ogrenci"] == 2  # b ve c
    assert j["grupsuz_aktif_ogrenci"] == 2  # b (yalnız pasif grupta) ve c (üyelik bitmiş)
    assert j["gruplar"]["aktif_grup"] == 2
    assert j["gruplar"]["toplam_kontenjan"] == 6
    assert j["gruplar"]["dolu"] == 2
    assert [(g["ad"], g["ogrenci_sayisi"], g["kontenjan"]) for g in j["gruplar"]["doluluk_listesi"]] == [
        ("U12", 1, 2),
        ("U10", 1, 4),
    ]
    programlar = {g["ad"]: g["program"] for g in j["gruplar"]["doluluk_listesi"]}
    assert programlar["U10"] == [
        {"gun": 1, "baslangic": "07:00:00", "bitis": "08:30:00"},
        {"gun": 3, "baslangic": "17:30:00", "bitis": "19:00:00"},
        {"gun": 5, "baslangic": "17:30:00", "bitis": "19:00:00"},
    ]
    assert programlar["U12"] == []
    assert j["antrenor"] == {"aktif": 1}
    assert j["bekleyen_odeme"] == {"adet": 2, "toplam_tutar": "1234.50"}
    assert {k["ad"] for k in j["son_kayitlar"]} == {"A", "B", "C"}  # aynı işlemde oluştuklarından sıra belirsiz
    assert {k["ad"]: k["foto_var"] for k in j["son_kayitlar"]} == {"A": True, "B": False, "C": False}


async def test_doluluk_listesi_en_cok_10_ve_son_kayit_5(istemci):
    baslik = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    async with SessionLocal() as s:
        s.add_all([Grup(ad=f"G{i:02d}", kontenjan=5) for i in range(12)])
        s.add_all([ogrenci(f"O{i}") for i in range(7)])
        await s.commit()
    j = (await istemci.get("/api/genel-bakis", headers=baslik)).json()
    assert j["gruplar"]["aktif_grup"] == 12
    assert len(j["gruplar"]["doluluk_listesi"]) == 10
    assert len(j["son_kayitlar"]) == 5


async def test_yetki(istemci):
    for eposta, rol in (("hoca@kulup.com", Rol.antrenor), ("veli@kulup.com", Rol.veli)):
        baslik = await giris(istemci, eposta, rol)
        assert (await istemci.get("/api/genel-bakis", headers=baslik)).status_code == 403
    assert (await istemci.get("/api/genel-bakis")).status_code == 401
