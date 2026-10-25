"""Şema kurallarının veritabanı düzeyinde gerçekten uygulandığını doğrular.
Hiçbiri uygulama koduna güvenmez: kural ihlali doğrudan veritabanından reddedilmelidir."""
from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app import kimlik
from app.db import SessionLocal
from app.models import (
    Antrenor,
    DersHakkiHareketi,
    DersOturumu,
    Grup,
    GrupProgrami,
    HareketTuru,
    IletisimKisisi,
    IletisimRolu,
    Odeme,
    OdemeYontemi,
    Ogrenci,
    OgrenciGrup,
    OgrenciPaketi,
    Paket,
    PaketTuru,
    Rol,
    Sayac,
    Yoklama,
    YoklamaDurum,
)
from tests.conftest import kullanici_olustur


async def kaydet(*nesneler):
    async with SessionLocal() as s:
        s.add_all(nesneler)
        await s.commit()


async def ogrenci_olustur(**ek) -> Ogrenci:
    o = Ogrenci(ad="Deneme", soyad="Öğrenci", dogum_tarihi=date(2016, 1, 3), **ek)
    await kaydet(o)
    return o


async def ihlal(kural: str, *nesneler):
    """Nesneleri kaydetmeyi dener ve veritabanının tam olarak `kural` adlı kısıtla reddetmesini bekler.
    Başka bir nedenle (ör. yanlış yabancı anahtar) reddedilirse test başarısız olur."""
    with pytest.raises((IntegrityError, DBAPIError)) as hata:
        await kaydet(*nesneler)
    assert kural in str(hata.value), f"beklenen kural: {kural}\ngelen: {hata.value}"


async def grup_ve_oturum():
    g = Grup(ad="A Grubu", kontenjan=10)
    await kaydet(g)
    ot = DersOturumu(grup_id=g.id, tarih=date(2026, 12, 2), baslangic=time(18, 0), bitis=time(19, 30))
    await kaydet(ot)
    return g, ot


# ---------- öğrenci ve iletişim ----------


async def test_kimlik_numarasi_ve_ozeti_birlikte_olmali():
    await ihlal("kimlik_cifti", Ogrenci(ad="A", soyad="B", dogum_tarihi=date(2016, 1, 3), kimlik_no_sifreli=b"x"))
    await ihlal("kimlik_cifti", Ogrenci(ad="A", soyad="B", dogum_tarihi=date(2016, 1, 3), kimlik_no_ozet="a" * 64))
    # İkisi de boş olabilir (içe aktarmada eksik veri) ve ikisi de dolu olabilir.
    await ogrenci_olustur()
    await ogrenci_olustur(kimlik_no_sifreli=kimlik.sifrele("10000000146"), kimlik_no_ozet=kimlik.ozet("10000000146"))


async def test_ayni_kimlik_numarasi_iki_kez_kaydedilemez():
    ozet = kimlik.ozet("10000000146")
    await ogrenci_olustur(kimlik_no_sifreli=kimlik.sifrele("10000000146"), kimlik_no_ozet=ozet)
    await ihlal("kimlik_no_ozet", 
        Ogrenci(
            ad="Baska",
            soyad="Kisi",
            dogum_tarihi=date(2015, 5, 5),
            kimlik_no_sifreli=kimlik.sifrele("10000000146"),
            kimlik_no_ozet=ozet,
        )
    )


async def test_ogrenci_basina_tek_birincil_iletisim_kisisi():
    o = await ogrenci_olustur()
    await kaydet(IletisimKisisi(ogrenci_id=o.id, rol=IletisimRolu.anne, ad_soyad="Anne", telefon="5", birincil=True))
    await kaydet(IletisimKisisi(ogrenci_id=o.id, rol=IletisimRolu.baba, ad_soyad="Baba", telefon="6"))
    await ihlal("uq_iletisim_kisisi_tek_birincil", IletisimKisisi(ogrenci_id=o.id, rol=IletisimRolu.baba, ad_soyad="Baba 2", telefon="7", birincil=True))


async def test_panel_hesabi_yalnizca_birincil_kisiye_baglanabilir():
    o = await ogrenci_olustur()
    veli = await kullanici_olustur("veli@kulup.com", Rol.veli)
    await ihlal("hesap_yalniz_birincilde", 
        IletisimKisisi(ogrenci_id=o.id, rol=IletisimRolu.baba, ad_soyad="Baba", telefon="6", kullanici_id=veli.id)
    )
    await kaydet(
        IletisimKisisi(
            ogrenci_id=o.id, rol=IletisimRolu.anne, ad_soyad="Anne", telefon="5", birincil=True, kullanici_id=veli.id
        )
    )


async def test_kardeslerde_ayni_veli_hesabi_birden_cok_ogrenciye_baglanir():
    veli = await kullanici_olustur("veli@kulup.com", Rol.veli)
    for _ in range(2):
        o = await ogrenci_olustur()
        await kaydet(
            IletisimKisisi(
                ogrenci_id=o.id, rol=IletisimRolu.anne, ad_soyad="Anne", telefon="5", birincil=True, kullanici_id=veli.id
            )
        )


# ---------- program ----------


async def test_program_kurallari():
    g = Grup(ad="A", kontenjan=10)
    await kaydet(g)
    await ihlal("kontenjan_pozitif", Grup(ad="Kontenjansız", kontenjan=0))
    await ihlal("gun_araligi", GrupProgrami(grup_id=g.id, gun=8, baslangic=time(18), bitis=time(19)))
    await ihlal("saat_sirasi", GrupProgrami(grup_id=g.id, gun=3, baslangic=time(19), bitis=time(18)))
    await kaydet(GrupProgrami(grup_id=g.id, gun=3, baslangic=time(18), bitis=time(19, 30)))
    await ihlal("uq_grup_programi_slot", GrupProgrami(grup_id=g.id, gun=3, baslangic=time(18), bitis=time(19)))  # aynı slot


async def test_ogrenci_ayni_gruba_ayni_anda_iki_kez_kayitli_olamaz_ama_ayrilip_donebilir():
    o = await ogrenci_olustur()
    g = Grup(ad="A", kontenjan=10)
    await kaydet(g)
    await kaydet(OgrenciGrup(ogrenci_id=o.id, grup_id=g.id, baslangic=date(2026, 1, 1), bitis=date(2026, 2, 1)))
    await kaydet(OgrenciGrup(ogrenci_id=o.id, grup_id=g.id, baslangic=date(2026, 3, 1)))
    await ihlal("uq_ogrenci_grup_acik", OgrenciGrup(ogrenci_id=o.id, grup_id=g.id, baslangic=date(2026, 4, 1)))


async def test_ders_oturumu_ayni_slotta_cift_olamaz():
    g, _ = await grup_ve_oturum()
    await ihlal("uq_ders_oturumu_slot", DersOturumu(grup_id=g.id, tarih=date(2026, 12, 2), baslangic=time(18, 0), bitis=time(19, 30)))


# ---------- yoklama ve defter ----------


async def test_ayni_ogrenci_ayni_derste_iki_yoklama_alamaz():
    o = await ogrenci_olustur()
    _, ot = await grup_ve_oturum()
    await kaydet(Yoklama(oturum_id=ot.id, ogrenci_id=o.id, durum=YoklamaDurum.geldi))
    await ihlal("uq_yoklama_oturum_ogrenci", Yoklama(oturum_id=ot.id, ogrenci_id=o.id, durum=YoklamaDurum.gelmedi))


async def yoklama_olustur():
    o = await ogrenci_olustur()
    _, ot = await grup_ve_oturum()
    y = Yoklama(oturum_id=ot.id, ogrenci_id=o.id, durum=YoklamaDurum.gelmedi)
    await kaydet(y)
    return o, y


async def test_devamsizlik_hareketi_tek_islemde_iki_sayaca_yazilir_ama_tekrarlanamaz():
    o, y = await yoklama_olustur()
    normal = DersHakkiHareketi(
        ogrenci_id=o.id, sayac=Sayac.normal, miktar=-1, tur=HareketTuru.devamsizlik, yoklama_id=y.id, yoklama_surum=0
    )
    telafi = DersHakkiHareketi(
        ogrenci_id=o.id, sayac=Sayac.telafi, miktar=1, tur=HareketTuru.devamsizlik, yoklama_id=y.id, yoklama_surum=0
    )
    await kaydet(normal, telafi)  # farklı sayaç: izinli
    # Arka plan işi yanlışlıkla ikinci kez çalışsa bile hak iki kez doğmaz.
    await ihlal("uq_hareket_yoklama_surum_tur_sayac", 
        DersHakkiHareketi(
            ogrenci_id=o.id, sayac=Sayac.telafi, miktar=1, tur=HareketTuru.devamsizlik, yoklama_id=y.id, yoklama_surum=0
        )
    )
    # Yoklama düzeltilip yeni sürüme geçince aynı türde hareket yeniden yazılabilir.
    await kaydet(
        DersHakkiHareketi(
            ogrenci_id=o.id, sayac=Sayac.telafi, miktar=1, tur=HareketTuru.devamsizlik, yoklama_id=y.id, yoklama_surum=1
        )
    )


async def test_yoklama_ve_surum_birlikte_dolu_veya_bos_olmali():
    o, y = await yoklama_olustur()
    await ihlal("yoklama_surum_birlikte", 
        DersHakkiHareketi(ogrenci_id=o.id, sayac=Sayac.normal, miktar=-1, tur=HareketTuru.ders_kullanimi, yoklama_id=y.id)
    )
    await ihlal("yoklama_surum_birlikte", 
        DersHakkiHareketi(ogrenci_id=o.id, sayac=Sayac.normal, miktar=-1, tur=HareketTuru.ders_kullanimi, yoklama_surum=0)
    )


async def test_defter_degistirilemez_ve_silinemez():
    o, y = await yoklama_olustur()
    h = DersHakkiHareketi(
        ogrenci_id=o.id, sayac=Sayac.normal, miktar=-1, tur=HareketTuru.ders_kullanimi, yoklama_id=y.id, yoklama_surum=0
    )
    await kaydet(h)
    async with SessionLocal() as s:
        with pytest.raises(DBAPIError, match="degistirilemez"):
            await s.execute(text("UPDATE ders_hakki_hareketi SET miktar = 5 WHERE id = :i"), {"i": h.id})
    async with SessionLocal() as s:
        with pytest.raises(DBAPIError, match="degistirilemez"):
            await s.execute(text("DELETE FROM ders_hakki_hareketi WHERE id = :i"), {"i": h.id})


async def test_hareket_kurallari():
    o, y = await yoklama_olustur()
    await ihlal("miktar_sifir_degil", DersHakkiHareketi(ogrenci_id=o.id, sayac=Sayac.normal, miktar=0, tur=HareketTuru.ders_kullanimi))
    # Manuel düzeltme nedensiz olmaz.
    await ihlal("duzeltme_nedeni", DersHakkiHareketi(ogrenci_id=o.id, sayac=Sayac.normal, miktar=1, tur=HareketTuru.manuel_duzeltme))
    await ihlal("duzeltme_nedeni", 
        DersHakkiHareketi(
            ogrenci_id=o.id, sayac=Sayac.normal, miktar=1, tur=HareketTuru.manuel_duzeltme, neden="   "
        )
    )
    await kaydet(
        DersHakkiHareketi(
            ogrenci_id=o.id, sayac=Sayac.normal, miktar=1, tur=HareketTuru.manuel_duzeltme, neden="Sayım hatası"
        )
    )
    # "iptal" türü bir hedef hareketi göstermek zorunda, başka türler göstermemeli.
    await ihlal("iptal_baglantisi", DersHakkiHareketi(ogrenci_id=o.id, sayac=Sayac.normal, miktar=-1, tur=HareketTuru.iptal))


async def test_bir_hareket_yalnizca_bir_kez_iptal_edilebilir():
    o, y = await yoklama_olustur()
    h = DersHakkiHareketi(
        ogrenci_id=o.id, sayac=Sayac.normal, miktar=-1, tur=HareketTuru.ders_kullanimi, yoklama_id=y.id, yoklama_surum=0
    )
    await kaydet(h)
    ters = dict(ogrenci_id=o.id, sayac=Sayac.normal, miktar=1, tur=HareketTuru.iptal, iptal_edilen_id=h.id)
    await kaydet(DersHakkiHareketi(**ters))
    await ihlal("uq_hareket_tek_iptal", DersHakkiHareketi(**ters))


async def test_ogrencisi_olan_hareket_icin_ogrenci_silinemez():
    o, y = await yoklama_olustur()
    await kaydet(DersHakkiHareketi(ogrenci_id=o.id, sayac=Sayac.normal, miktar=8, tur=HareketTuru.manuel_duzeltme, neden="Açılış"))
    async with SessionLocal() as s:
        with pytest.raises((IntegrityError, DBAPIError)):
            await s.execute(text("DELETE FROM ogrenci WHERE id = :i"), {"i": o.id})


# ---------- paket ve ödeme ----------


async def paket_olustur() -> Paket:
    p = Paket(ad="Aylık 8 ders", tur=PaketTuru.aylik, ders_sayisi=8, sure_ay=1, varsayilan_fiyat=Decimal("3000.00"))
    await kaydet(p)
    return p


async def test_paket_kurallari():
    await ihlal("ders_sayisi_pozitif", Paket(ad="Hatalı", tur=PaketTuru.aylik, ders_sayisi=0, sure_ay=1, varsayilan_fiyat=Decimal("1")))
    await ihlal("fiyat_negatif_degil", Paket(ad="Hatalı", tur=PaketTuru.aylik, ders_sayisi=8, sure_ay=1, varsayilan_fiyat=Decimal("-1")))


async def test_farkli_fiyat_ozel_fiyat_olarak_isaretlenmek_zorunda():
    o, p = await ogrenci_olustur(), await paket_olustur()
    temel = dict(ogrenci_id=o.id, paket_id=p.id, ders_sayisi=8, liste_fiyati=Decimal("3000"))
    await ihlal("ozel_fiyat_isareti", OgrenciPaketi(**temel, uygulanan_fiyat=Decimal("2500"), fiyat_ozel_mi=False))
    await kaydet(OgrenciPaketi(**temel, uygulanan_fiyat=Decimal("2500"), fiyat_ozel_mi=True))
    await kaydet(OgrenciPaketi(**temel, uygulanan_fiyat=Decimal("3000"), fiyat_ozel_mi=False))


async def test_bir_paket_yalnizca_bir_kez_yuklenir():
    o, p = await ogrenci_olustur(), await paket_olustur()
    op = OgrenciPaketi(
        ogrenci_id=o.id, paket_id=p.id, ders_sayisi=8, liste_fiyati=Decimal("3000"), uygulanan_fiyat=Decimal("3000")
    )
    await kaydet(op)
    yukleme = dict(ogrenci_id=o.id, sayac=Sayac.normal, miktar=8, tur=HareketTuru.paket_yuklemesi, ogrenci_paketi_id=op.id)
    await kaydet(DersHakkiHareketi(**yukleme))
    await ihlal("uq_hareket_paket_yuklemesi", DersHakkiHareketi(**yukleme))


async def test_odeme_tutari_pozitif_olmali():
    o, p = await ogrenci_olustur(), await paket_olustur()
    op = OgrenciPaketi(
        ogrenci_id=o.id, paket_id=p.id, ders_sayisi=8, liste_fiyati=Decimal("3000"), uygulanan_fiyat=Decimal("3000")
    )
    await kaydet(op)
    await ihlal("tutar_pozitif", Odeme(ogrenci_paketi_id=op.id, tutar=Decimal("0"), yontem=OdemeYontemi.nakit))
    await kaydet(Odeme(ogrenci_paketi_id=op.id, tutar=Decimal("3000"), yontem=OdemeYontemi.nakit))


# ---------- antrenör ----------


async def test_bir_kullanici_tek_antrenor_kaydina_baglanabilir():
    k = await kullanici_olustur("antrenor@kulup.com", Rol.antrenor)
    await kaydet(Antrenor(kullanici_id=k.id, ad_soyad="Antrenör 1"))
    await ihlal("uq_antrenor_kullanici_id", Antrenor(kullanici_id=k.id, ad_soyad="Antrenör 2"))


async def test_odeme_basina_bir_yukleme_ve_iptal_alanlari_birlikte():
    o, p = await ogrenci_olustur(), await paket_olustur()
    op = OgrenciPaketi(
        ogrenci_id=o.id, paket_id=p.id, ders_sayisi=8, liste_fiyati=Decimal("3000"), uygulanan_fiyat=Decimal("3000")
    )
    await kaydet(op)
    od = Odeme(ogrenci_paketi_id=op.id, tutar=Decimal("3000"), yontem=OdemeYontemi.nakit)
    await kaydet(od)
    await ihlal("iptal_alanlari_birlikte", Odeme(
        ogrenci_paketi_id=op.id, tutar=Decimal("1"), yontem=OdemeYontemi.nakit, iptal_nedeni="x"))
    yukleme = dict(ogrenci_id=o.id, sayac=Sayac.normal, miktar=8, tur=HareketTuru.paket_yuklemesi,
                   ogrenci_paketi_id=op.id, odeme_id=od.id)
    await kaydet(DersHakkiHareketi(**yukleme))
    await ihlal("uq_hareket_odeme_yuklemesi", DersHakkiHareketi(**yukleme))
