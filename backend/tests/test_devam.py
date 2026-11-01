"""Devam özeti: oran, son 30 gün, art arda devamsızlık, son dersler; yönetici ve antrenör uçları."""
from datetime import timedelta

from app.models import OturumDurum, Rol, Yoklama, YoklamaDurum
from tests.test_yoklama import (  # noqa: F401  (yonetici fixture)
    BUGUN, antrenor_hesabi, giris, grup_olustur, kaydet, ogrenci_olustur, oturum_olustur, uye_yap, yonetici,
)


async def _ders(grup, ogrenci, gun_once, durum, oturum_durum=OturumDurum.yapildi, telafi=False):
    ot = await oturum_olustur(grup, tarih=BUGUN - timedelta(days=gun_once), durum=oturum_durum)
    if durum:
        await kaydet(Yoklama(oturum_id=ot.id, ogrenci_id=ogrenci.id, durum=YoklamaDurum(durum), telafi_mi=telafi))


async def test_ogrenci_devam_ozeti(istemci, yonetici):
    g = await grup_olustur("U10")
    o = await ogrenci_olustur()
    await uye_yap(o, g)
    # 60 gün önce geldi; son 30 günde: geldi, geldi, gelmedi, gelmedi (en yenisi)
    await _ders(g, o, 60, "geldi")
    await _ders(g, o, 20, "geldi", telafi=True)
    await _ders(g, o, 10, "geldi")
    await _ders(g, o, 5, "gelmedi")
    await _ders(g, o, 2, "gelmedi")
    await _ders(g, o, 1, None)  # yoklaması alınmamış: sayılmaz
    await _ders(g, o, 3, "geldi", oturum_durum=OturumDurum.iptal)  # iptal: sayılmaz

    y = await istemci.get(f"/api/ogrenciler/{o.id}/devam", headers=yonetici)
    assert y.status_code == 200
    d = y.json()
    assert (d["katildi"], d["gelmedi"], d["oran"]) == (3, 2, 60)
    assert (d["son30_katildi"], d["son30_gelmedi"], d["son30_oran"]) == (2, 2, 50)
    assert d["ard_arda_gelmedi"] == 2
    assert [s["durum"] for s in d["son_dersler"]] == ["gelmedi", "gelmedi", "geldi", "geldi", "geldi"]
    assert d["son_dersler"][3]["telafi_mi"] is True and d["son_dersler"][0]["grup_ad"] == "U10"


async def test_hic_yoklama_yok(istemci, yonetici):
    o = await ogrenci_olustur()
    d = (await istemci.get(f"/api/ogrenciler/{o.id}/devam", headers=yonetici)).json()
    assert d["oran"] is None and d["son30_oran"] is None and d["son_dersler"] == [] and d["ard_arda_gelmedi"] == 0


async def test_grup_devami_ve_antrenor_ogrencilerim(istemci, yonetici):
    baslik, antrenor = await antrenor_hesabi(istemci, "a@kulup.com", "Ayşe Hoca")
    _, baska = await antrenor_hesabi(istemci, "b@kulup.com", "Başka Hoca")
    benim = await grup_olustur("U12", antrenor=antrenor)
    pasif = await grup_olustur("Eski", antrenor=antrenor, aktif=False)
    diger = await grup_olustur("U14", antrenor=baska)
    ali, zeynep, ayrilan = await ogrenci_olustur("Ali"), await ogrenci_olustur("Zeynep"), await ogrenci_olustur("Ayrılan")
    await uye_yap(ali, benim)
    await uye_yap(zeynep, benim)
    await uye_yap(ayrilan, benim, bitis=BUGUN - timedelta(days=1))
    await uye_yap(ali, diger)
    await uye_yap(zeynep, pasif)
    ot = await oturum_olustur(benim, tarih=BUGUN - timedelta(days=3), durum=OturumDurum.yapildi)
    await kaydet(Yoklama(oturum_id=ot.id, ogrenci_id=ali.id, durum=YoklamaDurum.geldi),
                 Yoklama(oturum_id=ot.id, ogrenci_id=zeynep.id, durum=YoklamaDurum.gelmedi))

    g = (await istemci.get(f"/api/gruplar/{benim.id}/devam", headers=yonetici)).json()
    assert [(s["ad"], s["devam"]["oran"]) for s in g["ogrenciler"]] == [("Ali", 100), ("Zeynep", 0)]

    y = await istemci.get("/api/antrenor/ogrencilerim", headers=baslik)
    assert y.status_code == 200
    assert [(gr["grup_ad"], [s["ad"] for s in gr["ogrenciler"]]) for gr in y.json()] == [("U12", ["Ali", "Zeynep"])]


async def test_yetki(istemci, yonetici):
    o = await ogrenci_olustur()
    g = await grup_olustur()
    antrenor, _ = await antrenor_hesabi(istemci, "a@kulup.com", "Ayşe Hoca")
    veli = await giris(istemci, "v@kulup.com", Rol.veli)
    for baslik in (antrenor, veli):
        assert (await istemci.get(f"/api/ogrenciler/{o.id}/devam", headers=baslik)).status_code == 403
        assert (await istemci.get(f"/api/gruplar/{g.id}/devam", headers=baslik)).status_code == 403
    assert (await istemci.get("/api/antrenor/ogrencilerim", headers=yonetici)).status_code == 403
    assert (await istemci.get("/api/antrenor/ogrencilerim", headers=veli)).status_code == 403
