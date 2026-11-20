"""Antrenör paneli: bugünün dersleri, yoklama durumu, eksik yoklama hatırlatması ve profil."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Antrenor, DenetimKaydi, DersOturumu, Kullanici, OturumDurum, Rol, TelafiPlani, Yoklama, YoklamaDurum
from tests.conftest import SIFRE
from tests.test_yoklama import (
    BUGUN,
    antrenor_hesabi,
    giris,
    grup_olustur,
    kaydet,
    ogrenci_olustur,
    uye_yap,
)


@pytest.fixture(autouse=True)
def sabit_saat(monkeypatch):
    """Bugün 12:00 (kulüp saati): saate bağlı sonuçlar günün saatinden bağımsız olsun."""
    an = datetime.combine(BUGUN, time(12), tzinfo=ZoneInfo(settings.saat_dilimi))
    monkeypatch.setattr("app.api.antrenor_paneli.simdi", lambda: an)


async def ders(grup, tarih=None, baslangic=time(9), bitis=time(10), antrenor=None, durum=OturumDurum.planli):
    ot = DersOturumu(
        grup_id=grup.id, tarih=tarih or BUGUN, baslangic=baslangic, bitis=bitis,
        antrenor_id=antrenor.id if antrenor else None, durum=durum,
    )
    await kaydet(ot)
    return ot


async def isaretle(oturum, *ogrenciler):
    await kaydet(*[Yoklama(oturum_id=oturum.id, ogrenci_id=o.id, durum=YoklamaDurum.geldi) for o in ogrenciler])


async def bugun_al(istemci, baslik):
    yanit = await istemci.get("/api/antrenor/bugun", headers=baslik)
    assert yanit.status_code == 200, yanit.text
    return yanit.json()


async def test_yalniz_kendi_dersleri_ve_yerine_bakilan(istemci):
    baslik, ben = await antrenor_hesabi(istemci, "ben@kulup.com", "Ben")
    _, baska = await antrenor_hesabi(istemci, "baska@kulup.com", "Baska")
    benim = await grup_olustur("Benim", antrenor=ben)
    onun = await grup_olustur("Onun", antrenor=baska)
    o1 = await ders(benim, baslangic=time(9), bitis=time(10))
    await ders(onun, baslangic=time(9), bitis=time(10))
    # Benim grubumda ama başka antrenör yerine bakıyor: bende görünmez.
    await ders(benim, baslangic=time(11), bitis=time(12), antrenor=baska)
    # Onun grubunda ama ben yerine bakıyorum: bende görünür.
    o4 = await ders(onun, baslangic=time(13), bitis=time(14), antrenor=ben)
    veri = await bugun_al(istemci, baslik)
    assert veri["tarih"] == str(BUGUN)
    assert [d["id"] for d in veri["dersler"]] == [str(o1.id), str(o4.id)]
    assert veri["dersler"][0]["grup"]["ad"] == "Benim"


async def test_sayilar_telafi_ve_yoklama_acik(istemci):
    baslik, ben = await antrenor_hesabi(istemci, "ben@kulup.com", "Ben")
    g = await grup_olustur("U10", antrenor=ben)
    a, b, c = [await ogrenci_olustur(ad) for ad in ("Ali", "Bora", "Can")]
    await uye_yap(a, g)
    await uye_yap(b, g)
    ot = await ders(g, baslangic=time(12, 10), bitis=time(13))  # 12:00'de açık (15 dk kuralı)
    uzak = await ders(g, baslangic=time(18), bitis=time(19))
    await kaydet(TelafiPlani(oturum_id=ot.id, ogrenci_id=c.id))
    veri = await bugun_al(istemci, baslik)
    d, u = veri["dersler"]
    assert d["id"] == str(ot.id) and d["beklenen_ogrenci"] == 3 and d["telafi_sayisi"] == 1
    assert d["yoklama_acik"] is True and u["yoklama_acik"] is False and u["id"] == str(uzak.id)
    assert veri["ozet"] == {"ders_sayisi": 2, "toplam_ogrenci": 5, "yoklama_bekleyen": 0}


async def test_yoklama_durumu_bekliyor_alindi_eksik(istemci):
    baslik, ben = await antrenor_hesabi(istemci, "ben@kulup.com", "Ben")
    g = await grup_olustur("U10", antrenor=ben)
    a, b = await ogrenci_olustur("Ali"), await ogrenci_olustur("Bora")
    await uye_yap(a, g)
    await uye_yap(b, g)
    bekleyen = await ders(g, baslangic=time(8), bitis=time(9))
    kismi = await ders(g, baslangic=time(9), bitis=time(10))
    tam = await ders(g, baslangic=time(10), bitis=time(11))
    iptal = await ders(g, baslangic=time(11), bitis=time(11, 30), durum=OturumDurum.iptal)
    await isaretle(kismi, a)
    await isaretle(tam, a, b)
    veri = await bugun_al(istemci, baslik)
    durum = {d["id"]: (d["yoklama_durumu"], d["yoklama_alinan"]) for d in veri["dersler"]}
    assert durum[str(bekleyen.id)] == ("bekliyor", 0)
    assert durum[str(kismi.id)] == ("eksik", 1)
    assert durum[str(tam.id)] == ("alindi", 2)
    assert durum[str(iptal.id)][0] == "iptal"
    # İptal dersler sayılmaz.
    assert veri["ozet"] == {"ders_sayisi": 3, "toplam_ogrenci": 6, "yoklama_bekleyen": 2}
    assert [e["id"] for e in veri["eksik_yoklamalar"]] == [str(bekleyen.id), str(kismi.id)]


async def test_eksik_yoklamalar_son_7_gun(istemci):
    baslik, ben = await antrenor_hesabi(istemci, "ben@kulup.com", "Ben")
    g = await grup_olustur("U10", antrenor=ben)
    a = await ogrenci_olustur("Ali")
    await uye_yap(a, g)
    dun = await ders(g, tarih=BUGUN - timedelta(days=1))
    alti = await ders(g, tarih=BUGUN - timedelta(days=6))
    await ders(g, tarih=BUGUN - timedelta(days=7))  # pencere dışı
    alindi = await ders(g, tarih=BUGUN - timedelta(days=2))
    await isaretle(alindi, a)
    await ders(g, tarih=BUGUN - timedelta(days=3), durum=OturumDurum.iptal)
    # Henüz bitmemiş bugünkü ders ve gelecek ders hatırlatılmaz.
    await ders(g, baslangic=time(13), bitis=time(14))
    await ders(g, tarih=BUGUN + timedelta(days=1))
    veri = await bugun_al(istemci, baslik)
    assert [e["id"] for e in veri["eksik_yoklamalar"]] == [str(alti.id), str(dun.id)]
    assert veri["ozet"]["yoklama_bekleyen"] == 0


async def test_siradaki_ders(istemci):
    baslik, ben = await antrenor_hesabi(istemci, "ben@kulup.com", "Ben")
    g = await grup_olustur("U10", antrenor=ben)
    a = await ogrenci_olustur("Ali")
    await uye_yap(a, g)
    await ders(g, baslangic=time(8), bitis=time(9))  # bitmiş ders hiçbir zaman sıradaki değildir
    surmekte = await ders(g, baslangic=time(11, 30), bitis=time(12, 30))
    sonraki = await ders(g, baslangic=time(15), bitis=time(16))
    assert (await bugun_al(istemci, baslik))["siradaki"] == str(surmekte.id)
    await isaretle(surmekte, a)  # yoklaması alınan ders sıradaki olmaz
    assert (await bugun_al(istemci, baslik))["siradaki"] == str(sonraki.id)
    async with SessionLocal() as s:
        ot = await s.get(DersOturumu, sonraki.id)
        ot.durum = OturumDurum.iptal
        await s.commit()
    assert (await bugun_al(istemci, baslik))["siradaki"] is None


async def test_ders_yoksa_bos(istemci):
    baslik, _ = await antrenor_hesabi(istemci, "ben@kulup.com", "Ben")
    veri = await bugun_al(istemci, baslik)
    assert veri["dersler"] == [] and veri["siradaki"] is None and veri["eksik_yoklamalar"] == []
    assert veri["ozet"] == {"ders_sayisi": 0, "toplam_ogrenci": 0, "yoklama_bekleyen": 0}


@pytest.mark.parametrize("yol", ["/api/antrenor/bugun", "/api/antrenor/profil"])
async def test_yetki(istemci, yol):
    yonetici = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    veli = await giris(istemci, "veli@kulup.com", Rol.veli)
    assert (await istemci.get(yol, headers=yonetici)).status_code == 403
    assert (await istemci.get(yol, headers=veli)).status_code == 403
    assert (await istemci.get(yol)).status_code == 401


async def test_profil_getir_ve_guncelle(istemci):
    baslik, ant = await antrenor_hesabi(istemci, "ben@kulup.com", "Ben Hoca")
    yanit = await istemci.get("/api/antrenor/profil", headers=baslik)
    assert yanit.json() == {"id": str(ant.id), "foto_var": False, "ad_soyad": "Ben Hoca", "telefon": None, "giris": "ben@kulup.com"}
    yanit = await istemci.patch(
        "/api/antrenor/profil", json={"ad_soyad": "  ahmet YILMAZ "}, headers=baslik
    )
    assert yanit.status_code == 200
    assert yanit.json() == {"id": str(ant.id), "foto_var": False, "ad_soyad": "Ahmet Yılmaz", "telefon": None, "giris": "ben@kulup.com"}
    async with SessionLocal() as s:
        a = await s.get(Antrenor, ant.id)
        k = (await s.execute(select(Kullanici).where(Kullanici.giris == "ben@kulup.com"))).scalar_one()
        assert (a.ad_soyad, a.telefon, k.ad_soyad) == ("Ahmet Yılmaz", None, "Ahmet Yılmaz")
        kayit = (
            await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "antrenor_profil_guncellendi"))
        ).scalar_one()
        assert kayit.kullanici_id == k.id and kayit.hedef_id == str(ant.id)
    # Giriş değişmedi: aynı bilgiyle yeniden girilebilir.
    assert (await istemci.post("/api/auth/login", json={"giris": "ben@kulup.com", "sifre": SIFRE})).status_code == 200


async def test_profil_telefon_degistirilemez(istemci):
    baslik, _ = await antrenor_hesabi(istemci, "ben@kulup.com", "Ben")
    for govde in ({"telefon": "05551112233"}, {"ad_soyad": "Yeni Ad", "telefon": ""}):
        assert (await istemci.patch("/api/antrenor/profil", json=govde, headers=baslik)).status_code == 422
    yanit = await istemci.patch("/api/antrenor/profil", json={"ad_soyad": "Yeni Ad"}, headers=baslik)
    assert yanit.json()["telefon"] is None and yanit.json()["ad_soyad"] == "Yeni Ad"


async def test_profil_dogrulama(istemci):
    baslik, _ = await antrenor_hesabi(istemci, "ben@kulup.com", "Ben")

    def patch(g):
        return istemci.patch("/api/antrenor/profil", json=g, headers=baslik)

    assert (await patch({"ad_soyad": "   "})).status_code == 422
    assert (await patch({"ad_soyad": None})).status_code == 422
    assert (await patch({"giris": "baska@kulup.com"})).status_code == 422  # giriş değiştirilemez
    assert (await istemci.get("/api/antrenor/profil", headers=baslik)).json()["giris"] == "ben@kulup.com"
    yonetici = await giris(istemci, "yonetici@kulup.com", Rol.admin)
    assert (await istemci.patch("/api/antrenor/profil", json={"ad_soyad": "X"}, headers=yonetici)).status_code == 403
