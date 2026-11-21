"""Antrenör telafi planlama (dilim 1): yetki kapsamı, taşıma, planlar, öğrencilerim bakiyesi ve bildirimler."""
from datetime import timedelta

from uuid import uuid4

from sqlalchemy import select

from app import bildirim as bsvc
from app.db import SessionLocal
from app.models import BildirimDurum, BildirimTercihi, DenetimKaydi, Kullanici, Ogrenci, TelafiPlani
from app.oturumlar import simdi
from tests.test_bildirim import bildirimler, ortam
from tests.test_telafi import detay, duzelt, gun, hakli_ogrenci, plan_url
from tests.test_yoklama import (
    BUGUN,
    antrenor_hesabi,
    govde,
    grup_olustur,
    oturum_olustur,
    uye_yap,
    yonetici,  # noqa: F401  (fixture)
)

YETKISIZ_OTURUM = "Bu işlem için yetkiniz yok"
YETKISIZ_GRUP = "Yalnız kendi grubunuzdaki öğrenciler için planlama yapabilirsiniz"


async def kurulum(istemci, telafi=1):
    """Antrenör A (iki grup), antrenör B (bir grup); öğrenci A1 grubunda ve telafi hakkı var."""
    ba, a = await antrenor_hesabi(istemci, "a@kulup.com", "Ahmet")
    bb, b = await antrenor_hesabi(istemci, "b@kulup.com", "Burak")
    a1 = await grup_olustur("A1", antrenor=a)
    a2 = await grup_olustur("A2", antrenor=a)
    b1 = await grup_olustur("B1", antrenor=b)
    return ba, a, bb, b, a1, a2, b1


async def hakli(istemci, yonetici, grup, telafi=1, ad="Ali"):
    o = await hakli_ogrenci(istemci, yonetici, telafi=telafi, ad=ad)
    await uye_yap(o, grup)
    return o


def pl(ot, o, tasinan=None):
    g = {"ogrenci_id": str(o.id)}
    if tasinan is not None:
        g["tasinan_oturum_id"] = str(tasinan.id)
    return g


async def hata(yanit, kod, mesaj):
    assert (yanit.status_code, yanit.json()["detail"]) == (kod, mesaj)


async def test_antrenor_kendi_ogrencisini_kendi_dersine_planlar_ve_kaldirir(istemci, yonetici):
    ba, a, _, _, a1, a2, _ = await kurulum(istemci)
    o = await hakli(istemci, yonetici, a1)
    ot = await oturum_olustur(a2, gun(2))
    yanit = await istemci.post(plan_url(ot), json=pl(ot, o), headers=ba)
    assert yanit.status_code == 200
    assert {x["ogrenci_id"]: x["telafi_mi"] for x in yanit.json()["ogrenciler"]} == {str(o.id): True}
    async with SessionLocal() as s:
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "telafi_planlandi"))).scalar_one()
        plan = (await s.execute(select(TelafiPlani))).scalar_one()
        kul = (await s.execute(select(Kullanici).where(Kullanici.giris == "a@kulup.com"))).scalar_one()
    assert k.kullanici_id == kul.id and plan.olusturan_id == kul.id
    y = await istemci.delete(f"{plan_url(ot)}/{o.id}", headers=ba)
    assert y.status_code == 200 and y.json()["ogrenciler"] == []
    async with SessionLocal() as s:
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "telafi_iptal_edildi"))).scalar_one()
    assert k.kullanici_id == kul.id


async def test_baska_grubun_ogrencisi_403(istemci, yonetici):
    ba, a, _, _, a1, a2, b1 = await kurulum(istemci)
    o = await hakli(istemci, yonetici, b1)
    ot = await oturum_olustur(a2, gun(2))
    await hata(await istemci.post(plan_url(ot), json=pl(ot, o), headers=ba), 403, YETKISIZ_GRUP)
    await hata(await istemci.delete(f"{plan_url(ot)}/{o.id}", headers=ba), 403, YETKISIZ_GRUP)
    await hata(await istemci.get(f"/api/ogrenciler/{o.id}/telafi-adaylari", headers=ba), 403, YETKISIZ_GRUP)
    await hata(await istemci.get(f"/api/ogrenciler/{o.id}/telafi-planlari", headers=ba), 403, YETKISIZ_GRUP)
    # Eski üyelik (bitmiş) ve pasif grup da kapsam dışıdır.
    pasif = await grup_olustur("PASIF", antrenor=a, aktif=False)
    o2 = await hakli_ogrenci(istemci, yonetici, ad="Veli")
    await uye_yap(o2, pasif)
    await hata(await istemci.post(plan_url(ot), json=pl(ot, o2), headers=ba), 403, YETKISIZ_GRUP)
    assert (await istemci.post(plan_url(ot), json=pl(ot, o), headers=yonetici)).status_code == 200  # yönetici serbest


async def test_baskasinin_dersi_403_yerine_bakan_planlar_asil_antrenor_planlayamaz(istemci, yonetici):
    ba, a, bb, b, a1, _, b1 = await kurulum(istemci)
    o = await hakli(istemci, yonetici, a1)
    ot = await oturum_olustur(b1, gun(2))
    await hata(await istemci.post(plan_url(ot), json=pl(ot, o), headers=ba), 403, YETKISIZ_OTURUM)
    # B'nin grubunun dersine A yerine bakıyor.
    yerine = await oturum_olustur(b1, gun(3), antrenor=a)
    assert (await istemci.post(plan_url(yerine), json=pl(yerine, o), headers=ba)).status_code == 200
    # Asıl antrenör B kendi grubunun o dersine (A'nın öğrencisi için de) planlayamaz.
    o_b2 = await hakli_ogrenci(istemci, yonetici, ad="Cem")
    await hata(await istemci.post(plan_url(yerine), json=pl(yerine, o_b2), headers=bb), 403, YETKISIZ_OTURUM)
    await hata(await istemci.delete(f"{plan_url(yerine)}/{o.id}", headers=bb), 403, YETKISIZ_OTURUM)
    # A kendi grubunun dersini başkası verirken planlayamaz.
    a_dersi_b_verir = await oturum_olustur(a1, gun(4), antrenor=b)
    o_a2 = await hakli(istemci, yonetici, a1, ad="Deniz")
    await hata(await istemci.post(plan_url(a_dersi_b_verir), json=pl(a_dersi_b_verir, o_a2), headers=ba), 403, YETKISIZ_OTURUM)


async def test_mevcut_telafi_hatalari_antrenorle_de(istemci, yonetici):
    ba, a, _, _, a1, a2, _ = await kurulum(istemci)
    ot = await oturum_olustur(a2, gun(2))
    hak_yok = await hakli(istemci, yonetici, a1, telafi=0, ad="Hakyok")
    await hata(await istemci.post(plan_url(ot), json=pl(ot, hak_yok), headers=ba), 422, "Kullanılabilir telafi hakkı yok")
    o = await hakli(istemci, yonetici, a1, telafi=2, ad="Var")
    await hata(await istemci.post(plan_url(await oturum_olustur(a2, gun(-1))), json=pl(ot, o), headers=ba), 422, "Geçmiş derse telafi planlanamaz")
    iptal = await oturum_olustur(a2, gun(3))
    await istemci.post(f"/api/oturumlar/{iptal.id}/iptal", json={}, headers=yonetici)
    await hata(await istemci.post(plan_url(iptal), json=pl(iptal, o), headers=ba), 422, "İptal edilmiş derse telafi planlanamaz")
    await hata(await istemci.post(plan_url(await oturum_olustur(a1, gun(5))), json=pl(ot, o), headers=ba), 422, "Öğrenci bu grubun üyesi, telafi gerekmez")
    assert (await istemci.post(plan_url(ot), json=pl(ot, o), headers=ba)).status_code == 200
    await hata(await istemci.post(plan_url(ot), json=pl(ot, o), headers=ba), 409, "Öğrenci bu derse zaten telafi için eklendi")
    # Kontenjan dolu.
    dolu = await oturum_olustur(a2, gun(6))
    async with SessionLocal() as s:
        from app.models import Grup
        g = await s.get(Grup, a2.id)
        g.kontenjan = 1
        await s.commit()
    uye = await hakli_ogrenci(istemci, yonetici, telafi=0, ad="Uye")
    await uye_yap(uye, a2)
    await hata(await istemci.post(plan_url(dolu), json=pl(dolu, o), headers=ba), 409, "Bu derste boş yer yok")
    await hata(await istemci.post(plan_url(ot), json={"ogrenci_id": str(uuid4())}, headers=ba), 404, "Öğrenci bulunamadı")


async def test_tasima_atomik_ve_denetim(istemci, yonetici):
    ba, a, bb, b, a1, a2, b1 = await kurulum(istemci)
    o = await hakli(istemci, yonetici, a1, telafi=1)
    eski = await oturum_olustur(a2, gun(2))
    yeni = await oturum_olustur(a2, gun(3))
    dolu = await oturum_olustur(a2, gun(4))
    assert (await istemci.post(plan_url(eski), json=pl(eski, o), headers=ba)).status_code == 200
    async with SessionLocal() as s:
        from app.models import Grup
        g = await s.get(Grup, a2.id)
        g.kontenjan = 1
        await s.commit()
    # Dolu derse taşıma reddedilir: eski plan yerinde kalır.
    d = await oturum_olustur(a1, gun(7))  # kendi grubu dersi: üyelik hatası
    await hata(await istemci.post(plan_url(d), json=pl(d, o, eski), headers=ba), 422, "Öğrenci bu grubun üyesi, telafi gerekmez")
    async with SessionLocal() as s:
        assert [p.oturum_id for p in (await s.execute(select(TelafiPlani))).scalars()] == [eski.id]
    # Başarılı taşıma (kontenjan 1, ders boş).
    yanit = await istemci.post(plan_url(yeni), json=pl(yeni, o, eski), headers=ba)
    assert yanit.status_code == 200
    async with SessionLocal() as s:
        assert [p.oturum_id for p in (await s.execute(select(TelafiPlani))).scalars()] == [yeni.id]
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "telafi_tasindi"))).scalar_one()
    assert k.hedef_id == str(yeni.id) and k.detay == {"ogrenci_id": str(o.id), "eski_oturum_id": str(eski.id)}
    assert await detay(istemci, yonetici, o) == {"normal": 0, "telafi": 1, "kullanilabilir_telafi": 0}
    # Dolu ders: biri yer tutar, taşıma 409 ile geri alınır.
    uye = await hakli_ogrenci(istemci, yonetici, telafi=0, ad="Uye")
    await uye_yap(uye, a2)
    await hata(await istemci.post(plan_url(dolu), json=pl(dolu, o, yeni), headers=ba), 409, "Bu derste boş yer yok")
    async with SessionLocal() as s:
        assert [p.oturum_id for p in (await s.execute(select(TelafiPlani))).scalars()] == [yeni.id]
    # Planı olmayan ders, başkasının dersi, yoklamalı plan, aynı ders.
    await hata(await istemci.post(plan_url(eski), json=pl(eski, o, dolu), headers=ba), 404, "Telafi planı bulunamadı")
    await hata(await istemci.post(plan_url(yeni), json=pl(yeni, o, yeni), headers=ba), 409, "Öğrenci bu derse zaten telafi için eklendi")


async def test_tasima_baskasinin_planini_ve_yoklamalisini_tasiyamaz(istemci, yonetici):
    ba, a, bb, b, a1, a2, b1 = await kurulum(istemci)
    o = await hakli(istemci, yonetici, a1, telafi=2)
    b_dersi = await oturum_olustur(b1, gun(2))
    yeni = await oturum_olustur(a2, gun(3))
    assert (await istemci.post(plan_url(b_dersi), json=pl(b_dersi, o), headers=yonetici)).status_code == 200
    # Plan B'nin dersinde: A taşıyamaz, kaldıramaz.
    await hata(await istemci.post(plan_url(yeni), json=pl(yeni, o, b_dersi), headers=ba), 403, YETKISIZ_OTURUM)
    async with SessionLocal() as s:
        assert [p.oturum_id for p in (await s.execute(select(TelafiPlani))).scalars()] == [b_dersi.id]
    # Yönetici taşıyabilir.
    assert (await istemci.post(plan_url(yeni), json=pl(yeni, o, b_dersi), headers=yonetici)).status_code == 200
    # Yoklaması alınmış plan taşınamaz.
    bugun_ders = await oturum_olustur(a2, BUGUN)
    assert (await istemci.post(plan_url(bugun_ders), json=pl(bugun_ders, o), headers=ba)).status_code == 200
    await istemci.put(f"/api/oturumlar/{bugun_ders.id}/yoklama", json=govde((o, "geldi")), headers=ba)
    hedef = await oturum_olustur(a2, gun(9))
    await hata(await istemci.post(plan_url(hedef), json=pl(hedef, o, bugun_ders), headers=ba), 409, "Yoklaması alınmış telafi geri alınamaz")


async def test_planlar_iptal_edilebilir_adaylar_ve_ogrenci_telafisi(istemci, yonetici):
    ba, a, bb, b, a1, a2, b1 = await kurulum(istemci)
    o = await hakli(istemci, yonetici, a1, telafi=3)
    kendi = await oturum_olustur(a2, gun(2))
    baskasi = await oturum_olustur(b1, gun(3))
    yoklamali = await oturum_olustur(a2, BUGUN)
    for ot in (kendi, baskasi, yoklamali):
        assert (await istemci.post(plan_url(ot), json=pl(ot, o), headers=yonetici)).status_code == 200
    await istemci.put(f"/api/oturumlar/{yoklamali.id}/yoklama", json=govde((o, "geldi")), headers=ba)
    planlar = (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-planlari", headers=ba)).json()
    assert {p["oturum_id"]: p["iptal_edilebilir"] for p in planlar} == {
        str(kendi.id): True, str(baskasi.id): False, str(yoklamali.id): False,
    }
    yon = (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-planlari", headers=yonetici)).json()
    assert {p["oturum_id"]: p["iptal_edilebilir"] for p in yon} == {
        str(kendi.id): True, str(baskasi.id): True, str(yoklamali.id): False,
    }
    # Adaylar yalnız antrenörün kendi dersleri (kendi grubu hariç, planlılar hariç).
    await oturum_olustur(a2, gun(5))
    await oturum_olustur(b1, gun(5))
    adaylar = (await istemci.get(f"/api/ogrenciler/{o.id}/telafi-adaylari", headers=ba)).json()
    assert [x["oturum"]["grup"]["ad"] for x in adaylar] == ["A2"]
    # Ayrıntı ucu.
    d = (await istemci.get(f"/api/antrenor/ogrenciler/{o.id}/telafi", headers=ba)).json()
    assert d["kullanilabilir"] == 0 and d["son_kullanma"] is None
    assert len(d["planlar"]) == 3
    await duzelt(istemci, yonetici, o, "telafi", 1)
    d = (await istemci.get(f"/api/antrenor/ogrenciler/{o.id}/telafi", headers=ba)).json()
    assert d["kullanilabilir"] == 1
    yanit = await istemci.get(f"/api/antrenor/ogrenciler/{o.id}/telafi", headers=bb)
    await hata(yanit, 404, "Öğrenci bulunamadı")
    # ogrencilerim: telafi bakiyesi (defter sayacı).
    gr = (await istemci.get("/api/antrenor/ogrencilerim", headers=ba)).json()
    satir = next(s for g in gr for s in g["ogrenciler"] if s["ogrenci_id"] == str(o.id))
    assert satir["telafi_bakiyesi"] == 3  # 4 hak - 1 kullanılan (yoklamalı geldi)


# ---------- bildirimler ----------


async def bildirimli(istemci, yonetici, **kw):
    ba, a, bb, b, a1, a2, b1 = await kurulum(istemci)
    ogr_id, kul_id, kisi_id = await ortam(**kw)
    async with SessionLocal() as s:
        o = await s.get(Ogrenci, ogr_id)
    await uye_yap(o, a1)
    assert (await duzelt(istemci, yonetici, o, "telafi", 2)).status_code == 200
    return ba, a1, a2, b1, o, kul_id, kisi_id


async def test_bildirim_planlama_tasima_kaldirma(istemci, yonetici):
    ba, a1, a2, b1, o, kul_id, kisi_id = await bildirimli(istemci, yonetici)
    eski = await oturum_olustur(a2, gun(2))
    yeni = await oturum_olustur(a2, gun(3))
    once = simdi()
    assert (await istemci.post(plan_url(eski), json=pl(eski, o), headers=ba)).status_code == 200
    liste = await bildirimler("telafi_planlandi")
    assert {b.kanal.value for b in liste} == {"whatsapp", "push"}
    assert all(b.alici_iletisim_id == kisi_id and b.durum == BildirimDurum.bekliyor and b.yoklama_id is None for b in liste)
    # Geri alma penceresi kadar bekletilir.
    assert all(timedelta(minutes=2) < b.planli_zaman - once < timedelta(minutes=4) for b in liste)
    async with SessionLocal() as s:
        metin = await bsvc.metin_olustur(s, liste[0])
    d = eski.tarih
    assert metin == f"Rota Performans Akademi: {o.ad} için {d.strftime('%d.%m.%Y')} 00:00 A2 dersine telafi planlandı."
    # Pencerede taşıma: eski bildirim iptal, yeni derse "planlandı" gider (veli eskisini hiç görmedi).
    assert (await istemci.post(plan_url(yeni), json=pl(yeni, o, eski), headers=ba)).status_code == 200
    planlandi = await bildirimler("telafi_planlandi")
    assert [b.durum for b in planlandi if b.parametreler["oturum_id"] == str(eski.id)] == [BildirimDurum.iptal] * 2
    assert len([b for b in planlandi if b.durum == BildirimDurum.bekliyor and b.parametreler["oturum_id"] == str(yeni.id)]) == 2
    assert await bildirimler("telafi_tasindi") == []
    # Pencerede kaldırma: hiçbir şey gitmez.
    assert (await istemci.delete(f"{plan_url(yeni)}/{o.id}", headers=ba)).status_code == 200
    assert all(b.durum == BildirimDurum.iptal for b in await bildirimler())
    assert await bildirimler("telafi_iptal_edildi") == []


async def test_bildirim_gonderilmis_planin_tasinmasi_ve_kaldirilmasi(istemci, yonetici):
    ba, a1, a2, b1, o, kul_id, kisi_id = await bildirimli(istemci, yonetici)
    eski = await oturum_olustur(a2, gun(2))
    yeni = await oturum_olustur(a2, gun(3))
    assert (await istemci.post(plan_url(eski), json=pl(eski, o), headers=ba)).status_code == 200
    async with SessionLocal() as s:  # gönderilmiş say
        for b in await bildirimler("telafi_planlandi"):
            (await s.get(type(b), b.id)).durum = BildirimDurum.gonderildi
        await s.commit()
    assert (await istemci.post(plan_url(yeni), json=pl(yeni, o, eski), headers=ba)).status_code == 200
    tasindi = await bildirimler("telafi_tasindi")
    assert len(tasindi) == 2 and all(b.durum == BildirimDurum.bekliyor for b in tasindi)
    async with SessionLocal() as s:
        metin = await bsvc.metin_olustur(s, tasindi[0])
    assert metin == (
        f"Rota Performans Akademi: {o.ad} için telafi dersi {eski.tarih.strftime('%d.%m.%Y')} 00:00 A2 dersinden "
        f"{yeni.tarih.strftime('%d.%m.%Y')} 00:00 A2 dersine taşındı."
    )
    # Taşındı henüz gitmeden kaldırılırsa veli eski dersi bildiği için eski ders iptali gider.
    assert (await istemci.delete(f"{plan_url(yeni)}/{o.id}", headers=ba)).status_code == 200
    assert all(b.durum == BildirimDurum.iptal for b in await bildirimler("telafi_tasindi"))
    iptal = await bildirimler("telafi_iptal_edildi")
    assert len(iptal) == 2
    async with SessionLocal() as s:
        metin = await bsvc.metin_olustur(s, iptal[0])
    assert metin == (
        f"Rota Performans Akademi: {o.ad} için {eski.tarih.strftime('%d.%m.%Y')} 00:00 A2 dersindeki telafi planı kaldırıldı."
    )


async def test_bildirim_gonderilmis_planin_kaldirilmasi(istemci, yonetici):
    ba, a1, a2, b1, o, kul_id, kisi_id = await bildirimli(istemci, yonetici)
    ot = await oturum_olustur(a2, gun(2))
    assert (await istemci.post(plan_url(ot), json=pl(ot, o), headers=yonetici)).status_code == 200  # yönetici de bildirir
    async with SessionLocal() as s:
        for b in await bildirimler("telafi_planlandi"):
            (await s.get(type(b), b.id)).durum = BildirimDurum.gonderildi
        await s.commit()
    assert (await istemci.delete(f"{plan_url(ot)}/{o.id}", headers=yonetici)).status_code == 200
    iptal = await bildirimler("telafi_iptal_edildi")
    assert len(iptal) == 2 and all(b.durum == BildirimDurum.bekliyor for b in iptal)


async def test_bildirim_tercih_ve_kisi_kurallari(istemci, yonetici):
    ba, a, _, _, a1, a2, _ = await kurulum(istemci)
    ot = await oturum_olustur(a2, gun(2))
    # ders_plani tercihi kapalıysa bildirim yok (ders_hakki ayrı kategoridir).
    ogr_id, kul_id, _ = await ortam(ad="Tercih")
    async with SessionLocal() as s:
        s.add(BildirimTercihi(kullanici_id=kul_id, ders_plani=False))
        o = await s.get(Ogrenci, ogr_id)
        await s.commit()
    await uye_yap(o, a1)
    await duzelt(istemci, yonetici, o, "telafi", 1)
    assert (await istemci.post(plan_url(ot), json=pl(ot, o), headers=ba)).status_code == 200
    assert await bildirimler() == []
    # Birincil kişi yoksa yok; yalnız ders_gelmedi kapalı ise gider (farklı kategori).
    ogr2, kul2, _ = await ortam(ad="Digeri")
    async with SessionLocal() as s:
        s.add(BildirimTercihi(kullanici_id=kul2, ders_gelmedi=False, push=False))
        o2 = await s.get(Ogrenci, ogr2)
        await s.commit()
    await uye_yap(o2, a1)
    await duzelt(istemci, yonetici, o2, "telafi", 1)
    assert (await istemci.post(plan_url(ot), json=pl(ot, o2), headers=ba)).status_code == 200
    liste = await bildirimler("telafi_planlandi")
    assert [b.kanal.value for b in liste] == ["whatsapp"] and liste[0].ogrenci_id == ogr2


async def test_sentetik_ogrenciye_bildirim_yok(istemci, yonetici):
    ogr_id, _, _ = await ortam(ad="Sentetik")
    async with SessionLocal() as s:
        o = await s.get(Ogrenci, ogr_id)
        o.sentetik = True
        await s.commit()
    ot = await oturum_olustur(await grup_olustur("X"), gun(2))
    async with SessionLocal() as s:
        await bsvc.telafi_planlandi(s, ogr_id, ot.id, ot.tarih, ot.baslangic, "X", simdi())
        await bsvc.telafi_tasindi(s, ogr_id, ot.id, (ot.tarih, ot.baslangic, "X"), ot.id, (ot.tarih, ot.baslangic, "X"), simdi())
        await bsvc.telafi_kaldirildi(s, ogr_id, ot.id, ot.tarih, ot.baslangic, "X", simdi())
        await s.commit()
    assert await bildirimler() == []


async def test_bildirim_tasima_zinciri_basa_donerse_bildirim_yok(istemci, yonetici):
    ba, a1, a2, b1, o, kul_id, kisi_id = await bildirimli(istemci, yonetici)
    x = await oturum_olustur(a2, gun(2))
    y = await oturum_olustur(a2, gun(3))
    assert (await istemci.post(plan_url(x), json=pl(x, o), headers=ba)).status_code == 200
    async with SessionLocal() as s:  # "planlandı" gönderilmiş say: veli X'i biliyor
        for b in await bildirimler("telafi_planlandi"):
            (await s.get(type(b), b.id)).durum = BildirimDurum.gonderildi
        await s.commit()
    assert (await istemci.post(plan_url(y), json=pl(y, o, x), headers=ba)).status_code == 200
    assert len([b for b in await bildirimler("telafi_tasindi") if b.durum == BildirimDurum.bekliyor]) == 2
    assert (await istemci.post(plan_url(x), json=pl(x, o, y), headers=ba)).status_code == 200
    # Pencere içinde X -> Y -> X: bekleyen taşındı iptal, yenisi yazılmaz.
    assert all(b.durum != BildirimDurum.bekliyor for b in await bildirimler("telafi_tasindi"))
    assert len(await bildirimler("telafi_tasindi")) == 2


async def test_adaylar_tasima_kipinde_tutulan_hak_serbest_sayilir(istemci, yonetici):
    import pytest
    from app.ders_hakki import ay_sonu

    ba, a, bb, b, a1, a2, b1 = await kurulum(istemci)
    a3 = await grup_olustur("A3", antrenor=a)
    o = await hakli(istemci, yonetici, a1, telafi=0)
    x = await oturum_olustur(a2, BUGUN)
    sonraki = ay_sonu(BUGUN) + timedelta(days=1)
    if (sonraki - BUGUN).days > 30:
        pytest.skip("Ay başı: sonraki ay aday penceresine sığmıyor")
    await oturum_olustur(a3, BUGUN)
    await oturum_olustur(a3, sonraki)
    async with SessionLocal() as s:  # ay sonunda biten telafi hakkı (elle verilen hak süresizdir)
        from app.models import DersHakkiHareketi, HareketTuru, Sayac
        s.add(DersHakkiHareketi(
            ogrenci_id=o.id, sayac=Sayac.telafi, miktar=1, tur=HareketTuru.devamsizlik, son_kullanma=ay_sonu(BUGUN),
        ))
        await s.commit()
    assert (await istemci.post(plan_url(x), json=pl(x, o), headers=ba)).status_code == 200
    url = f"/api/ogrenciler/{o.id}/telafi-adaylari?baslangic={BUGUN}&bitis={BUGUN + timedelta(days=30)}"
    tarihler = lambda r: sorted(a["oturum"]["tarih"] for a in r.json())
    # Hak plan tarafından tutuluyor: liste süzülmeden gelir (sonraki ay da görünür).
    assert str(sonraki) in tarihler(await istemci.get(url, headers=ba))
    # Taşıma kipi: hak serbest sayılır, ay sonundan sonraki tarih elenir.
    r = await istemci.get(f"{url}&tasinan_oturum_id={x.id}", headers=ba)
    assert r.status_code == 200 and tarihler(r) == [str(BUGUN)]
    # Yetki ve plan denetimi.
    b_dersi = await oturum_olustur(b1, gun(2))
    await hata(await istemci.get(f"{url}&tasinan_oturum_id={b_dersi.id}", headers=ba), 403, YETKISIZ_OTURUM)
    bos = await oturum_olustur(a3, gun(1))
    await hata(await istemci.get(f"{url}&tasinan_oturum_id={bos.id}", headers=ba), 404, "Telafi planı bulunamadı")
