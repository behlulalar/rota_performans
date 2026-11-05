"""Duyurular: hedef kitle, kardeş tekilleştirme, izin / tercih / cihaz kuralları, WhatsApp bağlı değilken red, push gönderimi, istatistik."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app import duyuru as dsvc
from app.db import SessionLocal
from app.models import (
    Bildirim,
    BildirimDurum,
    BildirimKanal,
    BildirimTercihi,
    DenetimKaydi,
    Duyuru,
    DuyuruHedefTuru,
    IletisimKisisi,
    IletisimRolu,
    Ogrenci,
    OgrenciDurum,
    PushAbonelik,
    Rol,
    TelafiPlani,
)
from tests.conftest import kullanici_olustur
from tests.test_push import calistir, etkin, gonderilenler  # noqa: F401  (fixture)
from tests.test_yoklama import (
    BUGUN,
    giris,
    grup_olustur,
    kaydet,
    oturum_olustur,
    uye_yap,
    yonetici,  # noqa: F401  (fixture)
)

U = "/api/duyurular"
TUM = {"tur": "tum"}


async def veli_hesabi(eposta="veli@kulup.com", *, cihaz=True, tercih: dict | None = None):
    k = await kullanici_olustur(eposta, Rol.veli)
    async with SessionLocal() as s:
        if cihaz:
            s.add(PushAbonelik(kullanici_id=k.id, endpoint=f"https://push.test/{k.id}", p256dh="p" * 20, auth="a" * 10))
        if tercih is not None:
            s.add(BildirimTercihi(kullanici_id=k.id, **tercih))
        await s.commit()
    return k.id


async def ogrenci(ad, soyad="Test", *, kullanici_id=None, izin=True, telefon=None, durum=OgrenciDurum.aktif,
                  birincil=True):
    # Varsayılan telefon öğrenciye özgüdür (aynı telefon, tekilleştirme testlerinde açıkça verilir).
    telefon = telefon or f"+90555{uuid.uuid4().int % 10**7:07d}"
    async with SessionLocal() as s:
        o = Ogrenci(ad=ad, soyad=soyad, dogum_tarihi=date(2015, 1, 1), durum=durum)
        s.add(o)
        await s.flush()
        if birincil:
            s.add(IletisimKisisi(
                ogrenci_id=o.id, rol=IletisimRolu.anne, ad_soyad=f"Anne {ad}", telefon=telefon, birincil=True,
                whatsapp_izni=izin, kullanici_id=kullanici_id,
            ))
        await s.commit()
        return o


def hedef_oturum(ot):
    return {"tur": "oturum", "oturum_id": str(ot.id)}


def hedef_grup(*gruplar):
    return {"tur": "grup", "grup_idleri": [str(g.id) for g in gruplar]}


async def onizle(istemci, yonetici, hedef, kanallar=None):
    govde = {"hedef": hedef}
    if kanallar:
        govde["kanallar"] = kanallar
    y = await istemci.post(f"{U}/onizleme", json=govde, headers=yonetici)
    assert y.status_code == 200, y.text
    return y.json()


async def gonder(istemci, yonetici, hedef, metin="Yarın ders yok.", baslik="Ders iptali", kanallar=None):
    return await istemci.post(
        U, json={"baslik": baslik, "metin": metin, "hedef": hedef, "kanallar": kanallar or {"push": True}}, headers=yonetici
    )


async def bildirimler():
    async with SessionLocal() as s:
        return list((await s.execute(select(Bildirim).order_by(Bildirim.id))).scalars())


# ---------- yetki ----------


async def test_yetki(istemci, yonetici):
    govde = {"baslik": "a", "metin": "b", "hedef": TUM}
    cagrilar = [
        ("post", f"{U}/onizleme", {"hedef": TUM}),
        ("post", U, govde),
        ("get", U, None),
        ("get", f"{U}/{uuid.uuid4()}", None),
    ]
    veli = await giris(istemci, "v@kulup.com", Rol.veli)
    antrenor = await giris(istemci, "a@kulup.com", Rol.antrenor)
    for yontem, url, g in cagrilar:
        kw = {"json": g} if g is not None else {}
        assert (await getattr(istemci, yontem)(url, **kw)).status_code == 401
        assert (await getattr(istemci, yontem)(url, headers=veli, **kw)).status_code == 403
        assert (await getattr(istemci, yontem)(url, headers=antrenor, **kw)).status_code == 403
    assert await bildirimler() == []


# ---------- hedef kitle ----------


async def test_hedef_oturum_uyeler_telafi_ve_dislananlar(istemci, yonetici):
    g, diger = await grup_olustur("A"), await grup_olustur("B")
    ot = await oturum_olustur(g, BUGUN + timedelta(days=3))
    uye = await ogrenci("Uye")
    ayrilmis = await ogrenci("Ayrilmis")
    sonradan = await ogrenci("Sonradan")
    pasif = await ogrenci("Pasif", durum=OgrenciDurum.pasif)
    baska = await ogrenci("Baska")
    telafici = await ogrenci("Telafici")
    await uye_yap(uye, g)
    await uye_yap(ayrilmis, g, baslangic=date(2020, 1, 1), bitis=BUGUN)  # ders gününden önce bitti
    await uye_yap(sonradan, g, baslangic=BUGUN + timedelta(days=10))  # ders gününden sonra katıldı
    await uye_yap(pasif, g)
    await uye_yap(baska, diger)
    await kaydet(TelafiPlani(oturum_id=ot.id, ogrenci_id=telafici.id))
    r = await onizle(istemci, yonetici, hedef_oturum(ot))
    assert r["ogrenci"] == 2  # uye + telafici
    assert r["alici"] == 2


async def test_hedef_grup_cok_grup_ve_tekrarsizlik(istemci, yonetici):
    a, b, c = await grup_olustur("A"), await grup_olustur("B"), await grup_olustur("C")
    x, y, z = await ogrenci("X"), await ogrenci("Y"), await ogrenci("Z")
    await uye_yap(x, a)
    await uye_yap(x, b)  # iki grupta: bir kez sayılır
    await uye_yap(y, b)
    await uye_yap(z, c)
    assert (await onizle(istemci, yonetici, hedef_grup(a, b)))["ogrenci"] == 2
    assert (await onizle(istemci, yonetici, hedef_grup(a, b, c)))["ogrenci"] == 3
    assert (await onizle(istemci, yonetici, hedef_grup(c)))["ogrenci"] == 1


async def test_hedef_tum_yalniz_aktif(istemci, yonetici):
    await ogrenci("A")
    await ogrenci("B")
    await ogrenci("P", durum=OgrenciDurum.pasif)
    assert (await onizle(istemci, yonetici, TUM))["ogrenci"] == 2


async def test_gecersiz_hedefler_422(istemci, yonetici):
    for h in (
        {"tur": "oturum"},
        {"tur": "oturum", "oturum_id": str(uuid.uuid4())},
        {"tur": "grup", "grup_idleri": []},
        {"tur": "grup", "grup_idleri": [str(uuid.uuid4())]},
        {"tur": "bilinmeyen"},
    ):
        assert (await istemci.post(f"{U}/onizleme", json={"hedef": h}, headers=yonetici)).status_code == 422, h


# ---------- alıcılar: kardeş tekilleştirme, izin, tercih, cihaz ----------


async def test_kardesler_tek_alici_tek_bildirim(istemci, yonetici):
    k = await veli_hesabi()
    g = await grup_olustur("A")
    ikinci = await ogrenci("Zeynep", "Aksoy", kullanici_id=k)
    birinci = await ogrenci("Ali", "Aksoy", kullanici_id=k)
    for o in (ikinci, birinci):
        await uye_yap(o, g)
    r = await onizle(istemci, yonetici, hedef_grup(g), {"push": True, "whatsapp": True})
    assert r == {"ogrenci": 2, "alici": 1, "push_alacak": 1, "push_yok": 0, "whatsapp_izinli": 1}
    y = await gonder(istemci, yonetici, hedef_grup(g))
    assert y.status_code == 201, y.text
    liste = await bildirimler()
    assert len(liste) == 1
    assert liste[0].ogrenci_id == birinci.id  # soyad, ad sırasında ilk öğrenci
    assert liste[0].kanal == BildirimKanal.push and liste[0].sablon == "duyuru"
    assert liste[0].duyuru_id is not None and liste[0].yoklama_id is None
    assert liste[0].durum == BildirimDurum.bekliyor


async def test_ayni_telefonlu_hesapsiz_kardesler_tek_whatsapp_alicisi(istemci, yonetici):
    g = await grup_olustur("A")
    for ad in ("A", "B"):
        await uye_yap(await ogrenci(ad, telefon="+905559998877"), g)
    r = await onizle(istemci, yonetici, hedef_grup(g), {"push": True, "whatsapp": True})
    assert r["alici"] == 1 and r["whatsapp_izinli"] == 1 and r["push_alacak"] == 0


async def test_kardeslerden_uygun_olmayan_ilk_ise_digeri_alir(istemci, yonetici):
    # Aynı telefon, hesap yok: ilk öğrencinin WhatsApp izni yok, ikincide var -> alıcı ikinci kişi.
    g = await grup_olustur("A")
    a = await ogrenci("A", telefon="+905559998877", izin=False)
    b = await ogrenci("B", telefon="+905559998877", izin=True)
    await uye_yap(a, g)
    await uye_yap(b, g)
    r = await onizle(istemci, yonetici, hedef_grup(g), {"push": True, "whatsapp": True})
    assert r["alici"] == 1 and r["whatsapp_izinli"] == 1


async def test_push_kurallari_hesap_cihaz_tercih(istemci, yonetici):
    g = await grup_olustur("A")
    tamam = await veli_hesabi("tamam@v.com")
    cihazsiz = await veli_hesabi("cihazsiz@v.com", cihaz=False)
    kapali = await veli_hesabi("kapali@v.com", tercih={"push": False})
    turler_kapali = await veli_hesabi("turler@v.com", tercih={"ders_gelmedi": False, "ders_hakki": False})
    for ad, kul in (("Tamam", tamam), ("Cihazsiz", cihazsiz), ("Kapali", kapali), ("Turler", turler_kapali), ("Hesapsiz", None)):
        await uye_yap(await ogrenci(ad, kullanici_id=kul, telefon=f"+90555000{len(ad):04d}"), g)
    r = await onizle(istemci, yonetici, hedef_grup(g))
    # Tür tercihleri (ders_gelmedi / ders_hakki) duyuruyu engellemez; kanal tercihi, hesap ve cihaz engeller.
    assert r["ogrenci"] == 5 and r["alici"] == 5
    assert r["push_alacak"] == 2 and r["push_yok"] == 3
    assert (await gonder(istemci, yonetici, hedef_grup(g))).status_code == 201
    alicilar = {b.ogrenci_id for b in await bildirimler()}
    async with SessionLocal() as s:
        adlar = {o.ad for o in (await s.execute(select(Ogrenci).where(Ogrenci.id.in_(alicilar)))).scalars()}
    assert adlar == {"Tamam", "Turler"}


async def test_whatsapp_izni_ve_tercihi(istemci, yonetici):
    g = await grup_olustur("A")
    wa_kapali = await veli_hesabi("wak@v.com", tercih={"whatsapp": False})
    acik = await veli_hesabi("acik@v.com", tercih={"push": False})  # push kapalı ama whatsapp açık
    await uye_yap(await ogrenci("Izinli", kullanici_id=acik, telefon="+905550000011"), g)
    await uye_yap(await ogrenci("Izinsiz", izin=False, telefon="+905550000012"), g)
    await uye_yap(await ogrenci("TercihKapali", kullanici_id=wa_kapali, telefon="+905550000013"), g)
    r = await onizle(istemci, yonetici, hedef_grup(g), {"push": True, "whatsapp": True})
    assert r["whatsapp_izinli"] == 1 and r["alici"] == 3


async def test_birincil_kisisi_olmayan_ogrenci_alici_degil(istemci, yonetici):
    await ogrenci("Kisisiz", birincil=False)
    r = await onizle(istemci, yonetici, TUM)
    assert r["ogrenci"] == 1 and r["alici"] == 0 and r["push_alacak"] == 0


# ---------- oluşturma kuralları ----------


async def test_whatsapp_bagli_degilken_422(istemci, yonetici):
    # Testlerde Evolution yapılandırılmamıştır: durum "yapilandirilmadi", WhatsApp'lı duyuru reddedilir.
    k = await veli_hesabi()
    await ogrenci("A", kullanici_id=k)
    for kanallar in ({"push": True, "whatsapp": True}, {"push": False, "whatsapp": True}):
        y = await gonder(istemci, yonetici, TUM, kanallar=kanallar)
        assert y.status_code == 422 and y.json()["detail"] == "WhatsApp bağlı değil"
    assert await bildirimler() == []
    async with SessionLocal() as s:
        assert (await s.execute(select(Duyuru))).first() is None


async def test_kanal_yok_alici_yok_ve_metin_siniri_422(istemci, yonetici):
    k = await veli_hesabi()
    await ogrenci("A", kullanici_id=k)
    assert (await gonder(istemci, yonetici, TUM, kanallar={"push": False, "whatsapp": False})).status_code == 422
    assert (await gonder(istemci, yonetici, TUM, metin="x" * 1001)).status_code == 422
    assert (await gonder(istemci, yonetici, TUM, metin="   ")).status_code == 422
    assert (await gonder(istemci, yonetici, TUM, baslik="")).status_code == 422
    assert (await gonder(istemci, yonetici, TUM, metin="x" * 1000)).status_code == 201
    # Alıcı kalmadıysa (hesapsız veli) duyuru oluşmaz.
    async with SessionLocal() as s:
        await s.execute(Bildirim.__table__.delete())
        await s.execute(PushAbonelik.__table__.delete())
        await s.commit()
    y = await gonder(istemci, yonetici, TUM)
    assert y.status_code == 422 and "alacak veli yok" in y.json()["detail"]


async def test_olusturma_kaydi_denetim_ve_oturum_bagi(istemci, yonetici):
    k = await veli_hesabi()
    g = await grup_olustur("A")
    ot = await oturum_olustur(g, BUGUN + timedelta(days=2))
    await uye_yap(await ogrenci("A", kullanici_id=k), g)
    y = await gonder(istemci, yonetici, hedef_oturum(ot), metin="Ders iptal.")
    assert y.status_code == 201
    d = y.json()
    assert d["oturum_id"] == str(ot.id) and d["hedef_tur"] == "oturum" and d["metin"] == "Ders iptal."
    assert d["kanallar"] == {"push": True, "whatsapp": False} and d["her_iki_kanal"] is False
    assert d["istatistik"]["push"]["toplam"] == 1 and d["istatistik"]["push"]["bekliyor"] == 1
    assert d["istatistik"]["whatsapp"]["toplam"] == 0
    assert d["hedef_ozet"].startswith("Ders: A · ")
    async with SessionLocal() as s:
        kayit = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "duyuru_gonderildi"))).scalar_one()
        assert kayit.hedef_id == d["id"] and kayit.detay["kuyruga"] == {"push": 1}
        assert "Ders iptal" not in json.dumps(kayit.detay)


async def test_ayni_duyuru_ayni_kisiye_ikinci_kez_eklenmez(istemci, yonetici):
    k = await veli_hesabi()
    await ogrenci("A", kullanici_id=k)
    y = await gonder(istemci, yonetici, TUM)
    assert y.status_code == 201
    async with SessionLocal() as s:
        d = await s.get(Duyuru, uuid.UUID(y.json()["id"]))
        kitle = await dsvc.kitleyi_coz(s, DuyuruHedefTuru.tum)
        assert await dsvc.kuyruga_ekle(s, d, kitle, datetime.now(timezone.utc)) == {"push": 0}
        await s.commit()
    assert len(await bildirimler()) == 1


# ---------- push gönderimi ----------


async def test_push_isci_duyuru_metnini_gonderir(istemci, yonetici, etkin, gonderilenler):  # noqa: F811
    k = await veli_hesabi()
    o = await ogrenci("Deniz", kullanici_id=k)
    metin = "Yarınki ders iptal edildi. {ad} {tarih} gibi süslü parantezler de sorun değil."
    assert (await gonder(istemci, yonetici, TUM, metin=metin)).status_code == 201
    sonuc = await calistir(datetime.now(timezone.utc) + timedelta(minutes=1))
    assert sonuc["gonderildi"] == 1
    (bilgi, veri), = gonderilenler["cagrilar"]
    yuk = json.loads(veri)
    assert yuk["govde"] == metin and yuk["url"] == "/panel" and yuk["baslik"] == "Rota Performans"
    assert str(o.id) not in veri
    (b,) = await bildirimler()
    assert b.durum == BildirimDurum.gonderildi


# ---------- liste, detay, istatistik ----------


async def test_liste_istatistik_detay(istemci, yonetici):
    g = await grup_olustur("A")
    kullanicilar = [await veli_hesabi(f"v{i}@v.com") for i in range(4)]
    for i, kul in enumerate(kullanicilar):
        await uye_yap(await ogrenci(f"Ogr{i}", f"Soy{i}", kullanici_id=kul), g)
    eski = (await gonder(istemci, yonetici, hedef_grup(g), baslik="Eski", metin="Eski mesaj")).json()
    yeni = (await gonder(istemci, yonetici, TUM, baslik="Yeni", metin="Yeni mesaj")).json()
    # Eski duyurunun durumlarını çeşitlendir.
    async with SessionLocal() as s:
        satirlar = list((await s.execute(
            select(Bildirim).where(Bildirim.duyuru_id == uuid.UUID(eski["id"])).order_by(Bildirim.id))).scalars())
        satirlar[0].durum, satirlar[1].durum = BildirimDurum.gonderildi, BildirimDurum.gonderildi
        satirlar[2].durum, satirlar[2].hata = BildirimDurum.hata, "abonelik yok"
        satirlar[3].durum = BildirimDurum.iptal
        await s.commit()
    liste = (await istemci.get(U, headers=yonetici)).json()
    assert [d["baslik"] for d in liste] == ["Yeni", "Eski"]  # en yeni başta
    assert liste[0]["hedef_ozet"] == "Tüm aktif öğrenciler" and liste[1]["hedef_ozet"] == "Grup: A"
    assert liste[1]["istatistik"]["push"] == {"toplam": 4, "gonderildi": 2, "bekliyor": 0, "hata": 1, "iptal": 1}
    assert liste[0]["istatistik"]["push"]["bekliyor"] == 4
    assert liste[1]["istatistik"]["whatsapp"] == {"toplam": 0, "gonderildi": 0, "bekliyor": 0, "hata": 0, "iptal": 0}

    d = (await istemci.get(f"{U}/{eski['id']}", headers=yonetici)).json()
    assert len(d["alicilar"]) == 4
    ilk = d["alicilar"][0]
    assert ilk["ogrenci_ad"] == "Ogr0 Soy0" and ilk["alici_ad"] == "Anne Ogr0" and ilk["kanal"] == "push"
    assert {a["durum"] for a in d["alicilar"]} == {"gonderildi", "hata", "iptal"}
    assert [a["hata"] for a in d["alicilar"] if a["durum"] == "hata"] == ["abonelik yok"]
    assert (await istemci.get(f"{U}/{uuid.uuid4()}", headers=yonetici)).status_code == 404


async def test_bildirim_yonetimi_duyuru_metnini_gosterir(istemci, yonetici):
    k = await veli_hesabi()
    await ogrenci("A", kullanici_id=k)
    await gonder(istemci, yonetici, TUM, metin="Salon bakımda.")
    y = await istemci.get("/api/bildirim-yonetimi?sablon=duyuru", headers=yonetici)
    assert y.status_code == 200
    (kayit,) = y.json()["kayitlar"]
    assert kayit["metin"] == "Salon bakımda." and kayit["sablon_etiket"] == "Duyuru"
