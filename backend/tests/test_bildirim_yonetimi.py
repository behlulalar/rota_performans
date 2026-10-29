"""Yönetici bildirim ekranı: yetki, özet, filtre, sayfalama, iptal / yeniden deneme."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Bildirim, BildirimDurum, BildirimKanal, DenetimKaydi, PushAbonelik, Rol
from tests.conftest import kullanici_olustur
from tests.test_bildirim import ortam
from tests.test_yoklama import giris, yonetici  # noqa: F401  (fixture)

U = "/api/bildirim-yonetimi"


async def ekle(ogrenci, kisi, *, durum=BildirimDurum.bekliyor, kanal=BildirimKanal.push, sablon="ders_gelmedi",
               planli=None, olusturma=None, deneme=0, hata=None):
    simdi = datetime.now(timezone.utc)
    async with SessionLocal() as s:
        b = Bildirim(
            ogrenci_id=ogrenci, alici_iletisim_id=kisi, kanal=kanal, sablon=sablon,
            parametreler={"tarih": "2026-11-02", "baslangic": "17:00", "bakiye": 2}, durum=durum,
            planli_zaman=planli or simdi, deneme=deneme, hata=hata, olusturma=olusturma or simdi,
        )
        s.add(b)
        await s.commit()
        return b.id


async def test_yetki(istemci):
    assert (await istemci.get(U)).status_code == 401
    assert (await istemci.get(f"{U}/ozet")).status_code == 401
    baslik = await giris(istemci, "veli@kulup.com", Rol.veli)
    assert (await istemci.get(U, headers=baslik)).status_code == 403
    assert (await istemci.get(f"{U}/ozet", headers=baslik)).status_code == 403
    assert (await istemci.post(f"{U}/1/iptal", headers=baslik)).status_code == 403
    assert (await istemci.post(f"{U}/1/yeniden-dene", headers=baslik)).status_code == 403


async def test_ozet_kanala_gore(istemci, yonetici):
    o, kul, kisi = await ortam()
    simdi = datetime.now(timezone.utc)
    await ekle(o, kisi, kanal=BildirimKanal.push, durum=BildirimDurum.gonderildi)
    await ekle(o, kisi, kanal=BildirimKanal.push, durum=BildirimDurum.bekliyor, planli=simdi - timedelta(minutes=5))
    await ekle(o, kisi, kanal=BildirimKanal.whatsapp, durum=BildirimDurum.hata)
    push = (await istemci.get(f"{U}/ozet?kanal=push", headers=yonetici)).json()
    assert push["son_7_gun"] == {"bekliyor": 1, "gonderildi": 1, "hata": 0, "iptal": 0} and push["geciken_bekleyen"] == 1
    wa = (await istemci.get(f"{U}/ozet?kanal=whatsapp", headers=yonetici)).json()
    assert wa["son_7_gun"] == {"bekliyor": 0, "gonderildi": 0, "hata": 1, "iptal": 0} and wa["geciken_bekleyen"] == 0
    tum = (await istemci.get(f"{U}/ozet", headers=yonetici)).json()
    assert tum["son_7_gun"] == {"bekliyor": 1, "gonderildi": 1, "hata": 1, "iptal": 0}
    assert (await istemci.get(f"{U}/ozet?kanal=sms", headers=yonetici)).status_code == 422


async def test_ozet(istemci, yonetici, monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "")
    o, kul, kisi = await ortam()
    simdi = datetime.now(timezone.utc)
    await ekle(o, kisi, durum=BildirimDurum.bekliyor, planli=simdi - timedelta(minutes=5))
    await ekle(o, kisi, durum=BildirimDurum.bekliyor, planli=simdi + timedelta(hours=1))
    await ekle(o, kisi, durum=BildirimDurum.gonderildi)
    await ekle(o, kisi, durum=BildirimDurum.hata)
    await ekle(o, kisi, durum=BildirimDurum.iptal, olusturma=simdi - timedelta(days=3))
    await ekle(o, kisi, durum=BildirimDurum.gonderildi, olusturma=simdi - timedelta(days=30))  # kapsam dışı
    async with SessionLocal() as s:
        for i, k in enumerate((kul, kul)):
            s.add(PushAbonelik(kullanici_id=k, endpoint=f"https://p.test/{i}", p256dh="p" * 20, auth="a" * 10))
        await s.commit()
    r = (await istemci.get(f"{U}/ozet", headers=yonetici)).json()
    assert r["son_7_gun"] == {"bekliyor": 2, "gonderildi": 1, "hata": 1, "iptal": 1}
    assert r["bugun"]["iptal"] == 0 and r["bugun"]["bekliyor"] == 2
    assert r["push_etkin"] is False
    assert r["push_cihaz_sayisi"] == 2 and r["push_kullanici_sayisi"] == 1
    assert r["geciken_bekleyen"] == 1


async def test_liste_alanlar_ve_filtreler(istemci, yonetici):
    o, _, kisi = await ortam(ad="Deniz")
    o2, _, kisi2 = await ortam(ad="Mert")
    b1 = await ekle(o, kisi, kanal=BildirimKanal.push, sablon="ders_gelmedi")
    b2 = await ekle(o2, kisi2, kanal=BildirimKanal.whatsapp, sablon="ders_hakki_bitti", durum=BildirimDurum.hata, hata="x")
    liste = (await istemci.get(U, headers=yonetici)).json()
    assert liste["toplam"] == 2
    assert [k["id"] for k in liste["kayitlar"]] == [b2, b1]  # yeni önce
    k = liste["kayitlar"][1]
    assert k["ogrenci"]["ad"] == "Deniz" and k["alici"] == {"ad_soyad": "Anne", "rol": "anne"}
    assert k["sablon_etiket"] == "Derse gelmedi" and "Deniz" in k["metin"] and "02.11.2026" in k["metin"]

    async def ids(sorgu):
        return [x["id"] for x in (await istemci.get(f"{U}?{sorgu}", headers=yonetici)).json()["kayitlar"]]

    assert await ids("durum=hata") == [b2]
    assert await ids("kanal=push") == [b1]
    assert await ids("sablon=ders_hakki_bitti") == [b2]
    assert await ids("q=mer") == [b2]
    assert await ids("q=Deniz%20Test") == [b1]
    bugun = datetime.now().date().isoformat()
    assert len(await ids(f"baslangic={bugun}&bitis={bugun}")) == 2
    assert await ids("bitis=2020-01-01") == []
    assert (await istemci.get(f"{U}?sablon=yok", headers=yonetici)).status_code == 422
    assert (await istemci.get(f"{U}?boyut=101", headers=yonetici)).status_code == 422
    assert (await istemci.get(f"{U}?baslangic=2026-02-02&bitis=2026-02-01", headers=yonetici)).status_code == 422


async def test_sayfalama(istemci, yonetici):
    o, _, kisi = await ortam()
    idler = [await ekle(o, kisi, sablon="ders_hakki_azaldi") for _ in range(5)]
    s1 = (await istemci.get(f"{U}?boyut=2&sayfa=1", headers=yonetici)).json()
    s3 = (await istemci.get(f"{U}?boyut=2&sayfa=3", headers=yonetici)).json()
    assert s1["toplam"] == 5 and [k["id"] for k in s1["kayitlar"]] == idler[::-1][:2]
    assert [k["id"] for k in s3["kayitlar"]] == [idler[0]]


async def denetim(islem):
    async with SessionLocal() as s:
        return list((await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == islem))).scalars())


async def test_iptal_kurallari(istemci, yonetici):
    o, _, kisi = await ortam()
    b = await ekle(o, kisi)
    r = await istemci.post(f"{U}/{b}/iptal", headers=yonetici)
    assert r.status_code == 200 and r.json()["durum"] == "iptal"
    assert (await istemci.post(f"{U}/{b}/iptal", headers=yonetici)).status_code == 409
    g = await ekle(o, kisi, durum=BildirimDurum.gonderildi)
    assert (await istemci.post(f"{U}/{g}/iptal", headers=yonetici)).status_code == 409
    assert (await istemci.post(f"{U}/999999/iptal", headers=yonetici)).status_code == 404
    kayit = await denetim("bildirim_iptal_edildi")
    assert len(kayit) == 1 and kayit[0].hedef_id == str(b)


async def test_yeniden_dene_kurallari(istemci, yonetici):
    o, _, kisi = await ortam()
    eski = datetime.now(timezone.utc) - timedelta(days=1)
    b = await ekle(o, kisi, durum=BildirimDurum.hata, deneme=5, hata="boom", planli=eski)
    r = await istemci.post(f"{U}/{b}/yeniden-dene", headers=yonetici)
    assert r.status_code == 200 and r.json()["durum"] == "bekliyor"
    async with SessionLocal() as s:
        x = await s.get(Bildirim, b)
        assert x.deneme == 0 and x.planli_zaman > eski
    assert (await istemci.post(f"{U}/{b}/yeniden-dene", headers=yonetici)).status_code == 409
    i = await ekle(o, kisi, durum=BildirimDurum.iptal)
    assert (await istemci.post(f"{U}/{i}/yeniden-dene", headers=yonetici)).status_code == 409
    assert (await istemci.post(f"{U}/999999/yeniden-dene", headers=yonetici)).status_code == 404
    kayit = await denetim("bildirim_yeniden_denendi")
    assert len(kayit) == 1 and kayit[0].hedef_id == str(b)
