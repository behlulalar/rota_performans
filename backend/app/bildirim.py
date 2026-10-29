"""Bildirim kuyruğu: olaylar kuyruğa yazılır, gönderim ayrı işçilerde yapılır (push: 4.3, WhatsApp: 4.4).

Kurallar:
- Alıcı yalnızca öğrencinin birincil iletişim kişisidir.
- Kuyruğa kişisel veri yazılmaz; metin gönderim anında `metin_olustur` ile kayıttan üretilir.
- `ders_gelmedi` yanlış işarete karşı GERI_ALMA_SURESI kadar bekletilir, yoklama düzelirse iptal edilir.
- Bakiye olayları (`ders_hakki_azaldi`, `ders_hakki_bitti`) defter hareketi yazıldıktan sonra tetiklenir.
Çağıran işlemi commit eder. Bu modül `ders_hakki`'nı içe aktarmaz (döngüyü önlemek için bakiyeyi kendisi okur)."""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bildirim import Bildirim, BildirimDurum, BildirimKanal, BildirimTercihi
from app.models.ogrenci import IletisimKisisi, Ogrenci
from app.models.paket import OgrenciPaketi, OgrenciPaketiDurum
from app.models.program import DersOturumu
from app.models.yoklama import DersHakkiHareketi, HareketTuru, Sayac, Yoklama

GERI_ALMA_SURESI = timedelta(minutes=3)
AZALDI_ESIGI = 2  # "son 2 ders"

DERS_GELMEDI = "ders_gelmedi"
DERS_HAKKI_AZALDI = "ders_hakki_azaldi"
DERS_HAKKI_BITTI = "ders_hakki_bitti"

# Şablon -> mesaj metni. {ad} ve {tarih} gibi alanlar gönderim anında doldurulur.
SABLONLAR: dict[str, str] = {
    DERS_GELMEDI: "Rota Performans Akademi: {ad}, {tarih} {saat} dersine katılmadı. Telafi hakkı tanımlanacaktır.",
    DERS_HAKKI_AZALDI: "Rota Performans Akademi: {ad} için {bakiye} ders hakkı kaldı. Yeni paket için kulüple iletişime geçebilirsiniz.",
    DERS_HAKKI_BITTI: "Rota Performans Akademi: {ad} için ders hakkı bitti. Derslere devam için yeni paket almanız gerekir.",
}

# Şablon -> kullanıcı tercihindeki tür anahtarı.
TERCIH_TURU = {DERS_GELMEDI: "ders_gelmedi", DERS_HAKKI_AZALDI: "ders_hakki", DERS_HAKKI_BITTI: "ders_hakki"}


async def kuyruga_ekle(
    session: AsyncSession,
    *,
    ogrenci_id: uuid.UUID,
    sablon: str,
    yoklama_id: uuid.UUID | None,
    simdi: datetime,
    parametreler: dict | None = None,
    bekleme: timedelta = timedelta(0),
) -> int:
    """Birincil kişi için açık kanallara bildirim yazar; eklenen satır sayısını verir.
    Aynı (yoklama, kanal, şablon) varsa tekrar eklenmez; yalnız iptal edilmiş satır yeniden etkinleşir."""
    if sablon not in SABLONLAR:
        raise ValueError(f"Bilinmeyen şablon: {sablon}")
    kisi = (
        await session.execute(
            select(IletisimKisisi).where(IletisimKisisi.ogrenci_id == ogrenci_id, IletisimKisisi.birincil.is_(True))
        )
    ).scalar_one_or_none()
    if kisi is None:
        return 0
    tercih = None
    if kisi.kullanici_id is not None:
        tercih = await session.get(BildirimTercihi, kisi.kullanici_id)
    # Tercih satırı yoksa (ya da hesap yoksa) varsayılanlar açıktır.
    if tercih is not None and not getattr(tercih, TERCIH_TURU[sablon]):
        return 0
    kanallar = []
    if kisi.whatsapp_izni and (tercih is None or tercih.whatsapp):
        kanallar.append(BildirimKanal.whatsapp)
    if kisi.kullanici_id is not None and (tercih is None or tercih.push):
        kanallar.append(BildirimKanal.push)
    eklenen = 0
    for kanal in kanallar:
        degerler = dict(
            ogrenci_id=ogrenci_id,
            alici_iletisim_id=kisi.id,
            kanal=kanal,
            sablon=sablon,
            parametreler=parametreler,
            yoklama_id=yoklama_id,
            durum=BildirimDurum.bekliyor,
            planli_zaman=simdi + bekleme,
            deneme=0,
        )
        sorgu = insert(Bildirim).values(**degerler)
        if yoklama_id is not None:
            sorgu = sorgu.on_conflict_do_update(
                index_elements=["yoklama_id", "kanal", "sablon"],
                index_where=Bildirim.yoklama_id.is_not(None),
                set_={"durum": BildirimDurum.bekliyor, "planli_zaman": degerler["planli_zaman"],
                      "parametreler": parametreler, "deneme": 0, "hata": None},
                where=Bildirim.durum == BildirimDurum.iptal,
            )
        sonuc = await session.execute(sorgu)
        eklenen += sonuc.rowcount
    return eklenen


async def gelmedi_iptal_et(session: AsyncSession, yoklama_id: uuid.UUID) -> int:
    """Yoklama düzeltildiğinde henüz gönderilmemiş `ders_gelmedi` bildirimlerini iptal eder.
    Gönderilmiş olanlara dokunulmaz."""
    sonuc = await session.execute(
        update(Bildirim)
        .where(
            Bildirim.yoklama_id == yoklama_id,
            Bildirim.sablon == DERS_GELMEDI,
            Bildirim.durum == BildirimDurum.bekliyor,
        )
        .values(durum=BildirimDurum.iptal)
    )
    return sonuc.rowcount


async def yoklama_isaretlendi(session: AsyncSession, yoklama: Yoklama, simdi: datetime) -> None:
    """Yoklamanın yeni durumuna göre `ders_gelmedi` kuyruğa alır (telafi dersinde devamsızlık bildirimi yoktur).
    Bakiye olayları, ders hakkı düşüldüğünde (geldi: hemen, gelmedi: 1 saat sonra işçide) ayrıca kontrol edilir."""
    if yoklama.telafi_mi:
        return
    if yoklama.durum.value == "gelmedi":
        oturum = await session.get(DersOturumu, yoklama.oturum_id)
        await kuyruga_ekle(
            session,
            ogrenci_id=yoklama.ogrenci_id,
            sablon=DERS_GELMEDI,
            yoklama_id=yoklama.id,
            simdi=simdi,
            parametreler={
                "oturum_id": str(oturum.id),
                "tarih": oturum.tarih.isoformat(),
                "baslangic": oturum.baslangic.strftime("%H:%M"),
            },
            bekleme=GERI_ALMA_SURESI,
        )
    elif yoklama.durum.value == "geldi":
        await bakiye_olaylari(session, yoklama.ogrenci_id, yoklama.id, simdi)


async def _normal_bakiye(session: AsyncSession, ogrenci_id: uuid.UUID) -> int:
    toplam = (
        await session.execute(
            select(func.coalesce(func.sum(DersHakkiHareketi.miktar), 0)).where(
                DersHakkiHareketi.ogrenci_id == ogrenci_id, DersHakkiHareketi.sayac == Sayac.normal
            )
        )
    ).scalar_one()
    return int(toplam)


async def _bu_donemde_var_mi(session: AsyncSession, ogrenci_id: uuid.UUID, sablon: str) -> bool:
    """Son paket yüklemesinden beri aynı şablonla (iptal olmayan) bildirim var mı?
    Bakiye aynı durumda kaldıkça (ör. -1, -2) tekrar bildirim üretilmez."""
    son_yukleme = (
        await session.execute(
            select(func.max(DersHakkiHareketi.zaman)).where(
                DersHakkiHareketi.ogrenci_id == ogrenci_id,
                DersHakkiHareketi.tur == HareketTuru.paket_yuklemesi,
            )
        )
    ).scalar_one()
    sorgu = select(Bildirim.id).where(
        Bildirim.ogrenci_id == ogrenci_id, Bildirim.sablon == sablon, Bildirim.durum != BildirimDurum.iptal
    )
    if son_yukleme is not None:
        sorgu = sorgu.where(Bildirim.olusturma > son_yukleme)
    return (await session.execute(sorgu.limit(1))).first() is not None


async def bakiye_olaylari(session: AsyncSession, ogrenci_id: uuid.UUID, yoklama_id: uuid.UUID, simdi: datetime) -> None:
    """Normal bakiye düştükten sonra çağrılır (defter satırları yazılmış/flush edilmiş olmalı).
    Bakiye tam 2 ise `ders_hakki_azaldi`; 0 ya da altındaysa ve ödenmiş paketi varsa `ders_hakki_bitti`."""
    bakiye = await _normal_bakiye(session, ogrenci_id)
    if bakiye == AZALDI_ESIGI:
        sablon, parametreler = DERS_HAKKI_AZALDI, {"bakiye": bakiye}
    elif bakiye <= 0:
        odenmis = (
            await session.execute(
                select(OgrenciPaketi.id)
                .where(OgrenciPaketi.ogrenci_id == ogrenci_id, OgrenciPaketi.durum == OgrenciPaketiDurum.odendi)
                .limit(1)
            )
        ).first()
        if odenmis is None:
            return
        sablon, parametreler = DERS_HAKKI_BITTI, {"bakiye": bakiye}
    else:
        return
    if await _bu_donemde_var_mi(session, ogrenci_id, sablon):
        return
    await kuyruga_ekle(
        session, ogrenci_id=ogrenci_id, sablon=sablon, yoklama_id=yoklama_id, simdi=simdi, parametreler=parametreler
    )


async def gonderilecekleri_al(
    session: AsyncSession, simdi: datetime, limit: int = 50, kanal: BildirimKanal | None = None
) -> list[Bildirim]:
    """Zamanı gelmiş bekleyen bildirimler. Satırlar kilitlenir (SKIP LOCKED): birden çok işçi aynı satırı almaz.
    Kilit, çağıranın işlemi bitene kadar sürer."""
    sorgu = select(Bildirim).where(Bildirim.durum == BildirimDurum.bekliyor, Bildirim.planli_zaman <= simdi)
    if kanal is not None:
        sorgu = sorgu.where(Bildirim.kanal == kanal)
    sorgu = sorgu.order_by(Bildirim.planli_zaman, Bildirim.id).limit(limit).with_for_update(skip_locked=True)
    return list((await session.execute(sorgu)).scalars().all())


async def metin_olustur(session: AsyncSession, bildirim: Bildirim) -> str:
    """Bildirimin mesaj metnini kayıttan üretir (öğrencinin adı gönderim anında okunur)."""
    sablon = SABLONLAR[bildirim.sablon]
    ogrenci = await session.get(Ogrenci, bildirim.ogrenci_id)
    p = bildirim.parametreler or {}
    tarih = ""
    if p.get("tarih"):
        y, a, g = p["tarih"].split("-")
        tarih = f"{g}.{a}.{y}"
    return sablon.format(ad=ogrenci.ad, tarih=tarih, saat=p.get("baslangic", ""), bakiye=p.get("bakiye", 0)).replace(
        "  ", " "
    )
