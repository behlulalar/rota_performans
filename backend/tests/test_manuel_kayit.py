"""Manuel gelir/gider: ekleme, doğrulama, iptal, yetki ve gelir raporuna (özet, günlük, aylık, CSV) yansıması."""
from datetime import date, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DenetimKaydi, Rol
from app.oturumlar import bugun
from tests.conftest import destek_baslik
from tests.test_gelir_raporu import odeme_ekle, paket_ekle, rapor, yonetici  # noqa: F401  (fixture)
from tests.test_paketler import giris

URL = "/api/manuel-kayitlar"


def kayit(tur="gelir", tutar="2000.00", tarih="2026-03-10", aciklama="Yaz kampı", yontem="nakit"):
    return {"tur": tur, "tutar": tutar, "tarih": tarih, "yontem": yontem, "aciklama": aciklama}


async def test_ekle_listele_iptal(istemci, yonetici):
    y = await istemci.post(URL, json=kayit(), headers=yonetici)
    assert y.status_code == 201, y.text
    j = y.json()
    assert j["tur"] == "gelir" and j["tutar"] == "2000.00" and j["iptal"] is False and j["olusturan"]
    await istemci.post(URL, json=kayit("gider", "1500", "2026-03-12", "Havuz kirası", "havale_eft"), headers=yonetici)
    await istemci.post(URL, json=kayit(tarih="2026-04-01"), headers=yonetici)

    liste = (await istemci.get(f"{URL}?yil=2026&ay=3", headers=yonetici)).json()
    assert [(k["tur"], k["aciklama"]) for k in liste] == [("gider", "Havuz kirası"), ("gelir", "Yaz kampı")]

    y = await istemci.post(f"{URL}/{j['id']}/iptal", json={"neden": "Yanlış girildi"}, headers=yonetici)
    assert y.status_code == 200 and y.json()["iptal"] is True and y.json()["iptal_nedeni"] == "Yanlış girildi"
    assert (await istemci.post(f"{URL}/{j['id']}/iptal", json={"neden": "Tekrar"}, headers=yonetici)).status_code == 409
    async with SessionLocal() as s:
        islemler = {k.islem for k in (await s.execute(select(DenetimKaydi))).scalars()}
    assert {"manuel_gelir_eklendi", "manuel_gider_eklendi", "manuel_gelir_iptal_edildi"} <= islemler


async def test_dogrulama(istemci, yonetici):
    yarin = (bugun() + timedelta(days=1)).isoformat()
    for govde in (
        kayit(tutar="0"), kayit(tutar="-5"), kayit(tutar="10.555"), kayit(aciklama="ab"), kayit(tur="baska"),
        kayit(tarih=yarin), {**kayit(), "fazla": 1},
    ):
        assert (await istemci.post(URL, json=govde, headers=yonetici)).status_code == 422, govde


async def test_rapora_yansir(istemci, yonetici):
    p = await paket_ekle()
    await odeme_ekle(p, "3000", date(2026, 3, 5))
    await odeme_ekle(p, "1000", date(2026, 2, 5))
    for g in (kayit("gelir", "2000", "2026-03-10"), kayit("gider", "1500", "2026-03-10", "Havuz kirası"),
              kayit("gider", "300", "2026-02-20", "Malzeme")):
        assert (await istemci.post(URL, json=g, headers=yonetici)).status_code == 201
    iptal = (await istemci.post(URL, json=kayit("gelir", "9999", "2026-03-11"), headers=yonetici)).json()
    await istemci.post(f"{URL}/{iptal['id']}/iptal", json={"neden": "Yanlış"}, headers=yonetici)

    j = (await rapor(istemci, yonetici, 2026, 3)).json()
    o = j["ozet"]
    assert (o["toplam_tahsilat"], o["manuel_gelir"], o["manuel_gider"], o["manuel_adedi"], o["net_gelir"]) == (
        "3000.00", "2000.00", "1500.00", 2, "3500.00")
    assert o["onceki_ay_net"] == "700.00" and o["degisim_yuzde"] == 400.0
    gun = {g["tarih"]: g["tutar"] for g in j["gunluk"]}
    assert gun["2026-03-05"] == "3000.00" and gun["2026-03-10"] == "500.00" and gun["2026-03-11"] == "0.00"
    ay = {(a["yil"], a["ay"]): a["tutar"] for a in j["aylik_seri"]}
    assert ay[(2026, 3)] == "3500.00" and ay[(2026, 2)] == "700.00"

    metin = (await istemci.get("/api/raporlar/gelir.csv?baslangic=2026-03-01&bitis=2026-03-31", headers=yonetici)).content.decode("utf-8-sig")
    assert "2026-03-10;;Manuel gelir;2000,00;Nakit;Geçerli;Yaz kampı;" in metin
    assert "2026-03-10;;Manuel gider;-1500,00;Nakit;Geçerli;Havuz kirası;" in metin
    assert "Manuel gelir;9999,00;Nakit;İptal" in metin


async def test_yetki_ve_destek_maskesi(istemci, yonetici):
    await istemci.post(URL, json=kayit(), headers=yonetici)
    antrenor = await giris(istemci, "hoca@kulup.com", Rol.antrenor)
    assert (await istemci.get(URL, headers=antrenor)).status_code == 403
    assert (await istemci.post(URL, json=kayit(), headers=antrenor)).status_code == 403
    destek = await destek_baslik(istemci)
    liste = (await istemci.get(f"{URL}?yil=2026&ay=3", headers=destek)).json()
    assert liste[0]["tutar"] is None and liste[0]["aciklama"] == "Yaz kampı"
    y = await istemci.post(URL, json=kayit(), headers=destek)
    assert y.status_code == 403 and y.json()["detail"] == "Teknik destek hesabı finansal işlem yapamaz"
    assert (await istemci.post(f"{URL}/{liste[0]['id']}/iptal", json={"neden": "abc"}, headers=destek)).status_code == 403
    o = (await istemci.get("/api/raporlar/gelir?yil=2026&ay=3", headers=destek)).json()["ozet"]
    assert o["manuel_gelir"] is None and o["net_gelir"] is None and o["manuel_adedi"] == 1
