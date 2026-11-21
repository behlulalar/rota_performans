"""Bildirim kuyruğu: olaylar kuyruğa yazılır, gönderim ayrı işçilerde yapılır (push: 4.3, WhatsApp: 4.4).

Kurallar:
- Alıcı yalnızca öğrencinin birincil iletişim kişisidir.
- Kuyruğa kişisel veri yazılmaz; metin gönderim anında `metin_olustur` ile kayıttan üretilir.
- `ders_gelmedi` yanlış işarete karşı GERI_ALMA_SURESI kadar bekletilir, yoklama düzelirse iptal edilir.
  Sebep bu sürede değişirse bekleyen bildirim yeni sebeple yeniden planlanır (metinde sebep ve sonucu yazar).
- Bakiye olayları (`ders_hakki_azaldi`, `ders_hakki_bitti`) defter hareketi yazıldıktan sonra tetiklenir.
Çağıran işlemi commit eder. Bu modül `ders_hakki`'nı içe aktarmaz (döngüyü önlemek için bakiyeyi kendisi okur)."""
import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ayarlar import KulupAyari
from app.models.duyuru import Duyuru
from app.models.bildirim import Bildirim, BildirimDurum, BildirimKanal, BildirimTercihi
from app.models.ogrenci import IletisimKisisi, Ogrenci
from app.models.paket import OgrenciPaketi, OgrenciPaketiDurum
from app.models.program import DersOturumu
from app.models.yoklama import DersHakkiHareketi, HareketTuru, Sayac, Yoklama

GERI_ALMA_SURESI = timedelta(minutes=3)
AZALDI_ESIGI = 2  # "son 2 ders"
# Yukarıdaki iki değer varsayılandır; kulüp ayarları (kulup_ayari) varsa oradan okunur.


async def ayarlari_oku(session: AsyncSession) -> tuple[timedelta, int]:
    """(geri alma süresi, "azaldı" eşiği). Ayar satırı yoksa varsayılanlar."""
    a = await session.get(KulupAyari, 1)
    if a is None:
        return GERI_ALMA_SURESI, AZALDI_ESIGI
    return timedelta(minutes=a.geri_alma_dakika), a.azaldi_esigi

DERS_GELMEDI = "ders_gelmedi"
DERS_HAKKI_AZALDI = "ders_hakki_azaldi"
DERS_HAKKI_BITTI = "ders_hakki_bitti"
DUYURU = "duyuru"
TELAFI_PLANLANDI = "telafi_planlandi"
TELAFI_TASINDI = "telafi_tasindi"
TELAFI_IPTAL = "telafi_iptal_edildi"
EK_DERS_PLANLANDI = "ek_ders_planlandi"
EK_DERS_TASINDI = "ek_ders_tasindi"
EK_DERS_IPTAL = "ek_ders_iptal_edildi"
TELAFI_SABLONLARI = (TELAFI_PLANLANDI, TELAFI_TASINDI, TELAFI_IPTAL)
EK_DERS_SABLONLARI = (EK_DERS_PLANLANDI, EK_DERS_TASINDI, EK_DERS_IPTAL)
# Plan türüne göre (planlandı, taşındı, kaldırıldı) şablonları.
PLAN_SABLONLARI = {"telafi": TELAFI_SABLONLARI, "ek_ders": EK_DERS_SABLONLARI}

# Devamsızlık sebebinin mesajdaki adı ve sonucu ({sebep}, {sonuc}). Sebepsiz eski kayıtlar eski metinle gider.
SEBEP_ETIKETI = {"izinli": "İzinli", "raporlu": "Raporlu", "yarisma": "Yarışma", "devamsiz": "Habersiz"}
MAZERETLI_SONUC = "Telafi hakkı tanımlanacaktır, ay sonuna kadar kullanılabilir."
DEVAMSIZ_SONUC = "Habersiz devamsızlıkta ders hakkı kullanılmış sayılır, telafi tanımlanmaz."
ESKI_SONUC = "Telafi hakkı tanımlanacaktır."


def gelmedi_alanlari(sebep: str | None) -> dict[str, str]:
    """`ders_gelmedi` metnindeki {sebep} ve {sonuc} alanları. Örn. " (Raporlu)" ve telafi cümlesi."""
    if sebep not in SEBEP_ETIKETI:
        return {"sebep": "", "sonuc": ESKI_SONUC}
    return {
        "sebep": f" ({SEBEP_ETIKETI[sebep]})",
        "sonuc": DEVAMSIZ_SONUC if sebep == "devamsiz" else MAZERETLI_SONUC,
    }


# Şablon -> mesaj metni. {ad} ve {tarih} gibi alanlar gönderim anında doldurulur.
SABLONLAR: dict[str, str] = {
    DERS_GELMEDI: "Rota Performans Akademi: {ad}, {tarih} {saat} dersine katılmadı{sebep}. {sonuc}",
    DERS_HAKKI_AZALDI: "Rota Performans Akademi: {ad} için {bakiye} ders hakkı kaldı. Yeni paket için kulüple iletişime geçebilirsiniz.",
    DERS_HAKKI_BITTI: "Rota Performans Akademi: {ad} için ders hakkı bitti. Derslere devam için yeni paket almanız gerekir.",
    TELAFI_PLANLANDI: "Rota Performans Akademi: {ad} için {tarih} {saat} {grup} dersine telafi planlandı.",
    TELAFI_TASINDI: "Rota Performans Akademi: {ad} için telafi dersi {eski_tarih} {eski_saat} {eski_grup} dersinden {tarih} {saat} {grup} dersine taşındı.",
    TELAFI_IPTAL: "Rota Performans Akademi: {ad} için {tarih} {saat} {grup} dersindeki telafi planı kaldırıldı.",
    EK_DERS_PLANLANDI: "Rota Performans Akademi: {ad} için {tarih} {saat} {grup} dersine ek ders planlandı.",
    EK_DERS_TASINDI: "Rota Performans Akademi: {ad} için ek ders {eski_tarih} {eski_saat} {eski_grup} dersinden {tarih} {saat} {grup} dersine taşındı.",
    EK_DERS_IPTAL: "Rota Performans Akademi: {ad} için {tarih} {saat} {grup} dersindeki ek ders planı kaldırıldı.",
    # Metin yöneticinin yazdığı duyurudur (`duyuru.metin`), `metin_olustur` doğrudan onu döndürür.
    DUYURU: "{metin}",
}

# WhatsApp için her kişisel şablonun aynı anlama gelen 3 söylenişi (mesajlar birebir aynı olmasın).
# Seçim bildirim kimliğine göre deterministiktir: `soylenis_sec`. Link yoktur.
# {ad}, {tarih}, {saat}, {bakiye}, {sebep}, {sonuc} doldurulur.
SOYLENISLER: dict[str, list[str]] = {
    DERS_GELMEDI: [
        "Rota Performans Akademi: {ad}, {tarih} {saat} dersine katılmadı{sebep}. {sonuc}",
        "Merhaba, Rota Performans Akademi'den yazıyoruz. {ad} {tarih} {saat} dersine gelemedi{sebep}. {sonuc}",
        "Rota Performans Akademi bilgilendirmesi: {ad} {tarih} {saat} dersinde yoktu{sebep}. {sonuc}",
    ],
    DERS_HAKKI_AZALDI: [
        "Rota Performans Akademi: {ad} için {bakiye} ders hakkı kaldı. Yeni paket için kulüple iletişime geçebilirsiniz.",
        "Merhaba, Rota Performans Akademi'den yazıyoruz. {ad} için yalnızca {bakiye} ders hakkı kaldı; yeni paket için bize ulaşabilirsiniz.",
        "Rota Performans Akademi bilgilendirmesi: {ad} adına {bakiye} ders hakkı kalmıştır. Yeni paket için kulüple görüşebilirsiniz.",
    ],
    TELAFI_PLANLANDI: [
        "Rota Performans Akademi: {ad} için {tarih} {saat} {grup} dersine telafi planlandı.",
        "Merhaba, Rota Performans Akademi'den yazıyoruz. {ad} için {tarih} {saat} {grup} dersine telafi dersi ayarlandı.",
        "Rota Performans Akademi bilgilendirmesi: {ad} adına {tarih} {saat} {grup} dersinde telafi planlanmıştır.",
    ],
    TELAFI_TASINDI: [
        "Rota Performans Akademi: {ad} için telafi dersi {eski_tarih} {eski_saat} {eski_grup} dersinden {tarih} {saat} {grup} dersine taşındı.",
        "Merhaba, Rota Performans Akademi'den yazıyoruz. {ad} için telafi dersi değişti: {eski_tarih} {eski_saat} {eski_grup} yerine {tarih} {saat} {grup} dersine katılacak.",
        "Rota Performans Akademi bilgilendirmesi: {ad} adına telafi dersi {eski_tarih} {eski_saat} {eski_grup} dersinden {tarih} {saat} {grup} dersine alınmıştır.",
    ],
    TELAFI_IPTAL: [
        "Rota Performans Akademi: {ad} için {tarih} {saat} {grup} dersindeki telafi planı kaldırıldı.",
        "Merhaba, Rota Performans Akademi'den yazıyoruz. {ad} için {tarih} {saat} {grup} dersine planlanan telafi iptal edildi.",
        "Rota Performans Akademi bilgilendirmesi: {ad} adına {tarih} {saat} {grup} dersindeki telafi planı kaldırılmıştır.",
    ],
    EK_DERS_PLANLANDI: [
        "Rota Performans Akademi: {ad} için {tarih} {saat} {grup} dersine ek ders planlandı.",
        "Merhaba, Rota Performans Akademi'den yazıyoruz. {ad} için {tarih} {saat} {grup} dersine ek ders ayarlandı.",
        "Rota Performans Akademi bilgilendirmesi: {ad} adına {tarih} {saat} {grup} dersinde ek ders planlanmıştır.",
    ],
    EK_DERS_TASINDI: [
        "Rota Performans Akademi: {ad} için ek ders {eski_tarih} {eski_saat} {eski_grup} dersinden {tarih} {saat} {grup} dersine taşındı.",
        "Merhaba, Rota Performans Akademi'den yazıyoruz. {ad} için ek ders değişti: {eski_tarih} {eski_saat} {eski_grup} yerine {tarih} {saat} {grup} dersine katılacak.",
        "Rota Performans Akademi bilgilendirmesi: {ad} adına ek ders {eski_tarih} {eski_saat} {eski_grup} dersinden {tarih} {saat} {grup} dersine alınmıştır.",
    ],
    EK_DERS_IPTAL: [
        "Rota Performans Akademi: {ad} için {tarih} {saat} {grup} dersindeki ek ders planı kaldırıldı.",
        "Merhaba, Rota Performans Akademi'den yazıyoruz. {ad} için {tarih} {saat} {grup} dersine planlanan ek ders iptal edildi.",
        "Rota Performans Akademi bilgilendirmesi: {ad} adına {tarih} {saat} {grup} dersindeki ek ders planı kaldırılmıştır.",
    ],
    DERS_HAKKI_BITTI: [
        "Rota Performans Akademi: {ad} için ders hakkı bitti. Derslere devam için yeni paket almanız gerekir.",
        "Merhaba, Rota Performans Akademi'den yazıyoruz. {ad} için ders hakkı sona erdi; derslere devam için yeni paket gerekiyor.",
        "Rota Performans Akademi bilgilendirmesi: {ad} adına ders hakkı kalmamıştır. Derslere devam edebilmesi için yeni paket almanız gerekir.",
    ],
}


def soylenis_sec(sablon: str, bildirim_id: int) -> str:
    """Kişisel şablonun WhatsApp söylenişi; bildirim kimliğine göre (id % 3) deterministik."""
    secenekler = SOYLENISLER[sablon]
    return secenekler[bildirim_id % len(secenekler)]


# Şablon -> kullanıcı tercihindeki tür anahtarı.
# `duyuru` burada YOKTUR: duyurular tür tercihlerine (ders_gelmedi / ders_hakki) tabi değildir,
# yalnızca kanal tercihlerine (push / whatsapp açık-kapalı) uyar. Bkz. app/duyuru.py.
TERCIH_TURU = {
    DERS_GELMEDI: "ders_gelmedi", DERS_HAKKI_AZALDI: "ders_hakki", DERS_HAKKI_BITTI: "ders_hakki",
    # Telafi ve ek ders planlama bildirimleri ayrı "ders_plani" tercihine bağlıdır (ders hakkı tercihinden bağımsız).
    TELAFI_PLANLANDI: "ders_plani", TELAFI_TASINDI: "ders_plani", TELAFI_IPTAL: "ders_plani",
    EK_DERS_PLANLANDI: "ders_plani", EK_DERS_TASINDI: "ders_plani", EK_DERS_IPTAL: "ders_plani",
}


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


def _ders_parametreleri(tarih: date, baslangic: time, grup_ad: str, onek: str = "") -> dict:
    return {f"{onek}tarih": tarih.isoformat(), f"{onek}baslangic": baslangic.strftime("%H:%M"), f"{onek}grup": grup_ad}


async def _bekleyen_telafi(
    session: AsyncSession, ogrenci_id: uuid.UUID, oturum_id: uuid.UUID, tur: str = "telafi"
) -> list[Bildirim]:
    """Öğrencinin bu oturum için henüz gönderilmemiş (geri alma penceresindeki) planlandı/taşındı bildirimleri
    (`tur`: telafi ya da ek_ders)."""
    planlandi, tasindi, _ = PLAN_SABLONLARI[tur]
    return list(
        (
            await session.execute(
                select(Bildirim)
                .where(
                    Bildirim.ogrenci_id == ogrenci_id,
                    Bildirim.sablon.in_((planlandi, tasindi)),
                    Bildirim.durum == BildirimDurum.bekliyor,
                    Bildirim.parametreler["oturum_id"].astext == str(oturum_id),
                )
                .with_for_update()
            )
        ).scalars()
    )


async def _telafi_kuyrugu(session: AsyncSession, ogrenci_id: uuid.UUID, sablon: str, parametreler: dict, simdi: datetime) -> None:
    ogrenci = await session.get(Ogrenci, ogrenci_id)
    if ogrenci is None or ogrenci.sentetik:
        return
    geri_alma, _ = await ayarlari_oku(session)
    await kuyruga_ekle(
        session, ogrenci_id=ogrenci_id, sablon=sablon, yoklama_id=None, simdi=simdi, parametreler=parametreler,
        bekleme=geri_alma,
    )


async def telafi_planlandi(
    session: AsyncSession, ogrenci_id: uuid.UUID, oturum_id: uuid.UUID, tarih: date, baslangic: time, grup_ad: str,
    simdi: datetime, tur: str = "telafi",
) -> None:
    """Telafi/ek ders planlandı: birincil kişiye, geri alma süresi kadar bekletilerek."""
    p = {"oturum_id": str(oturum_id), **_ders_parametreleri(tarih, baslangic, grup_ad)}
    await _telafi_kuyrugu(session, ogrenci_id, PLAN_SABLONLARI[tur][0], p, simdi)


async def telafi_tasindi(
    session: AsyncSession, ogrenci_id: uuid.UUID, eski_oturum_id: uuid.UUID, eski: tuple[date, time, str],
    oturum_id: uuid.UUID, yeni: tuple[date, time, str], simdi: datetime, tur: str = "telafi",
) -> None:
    """Telafi/ek ders taşındı. Eski plan için bildirim henüz gitmediyse (veli eskisini hiç görmedi) o iptal edilir:
    planlandı bildirimi ise yeni derse "planlandı", taşındı bildirimi ise ilk eski derse göre "taşındı" gider."""
    eski_p = {**_ders_parametreleri(*eski, onek="eski_"), "eski_oturum_id": str(eski_oturum_id)}
    planlandi, tasindi, _ = PLAN_SABLONLARI[tur]
    sablon = tasindi
    for b in await _bekleyen_telafi(session, ogrenci_id, eski_oturum_id, tur):
        b.durum = BildirimDurum.iptal
        if b.sablon == planlandi:
            sablon = planlandi
        else:
            eski_p = {k: v for k, v in (b.parametreler or {}).items() if k.startswith("eski_")}
            sablon = tasindi
    if sablon == tasindi and eski_p.get("eski_oturum_id") == str(oturum_id):
        return  # zincir başladığı derse döndü: veli için değişen bir şey yok
    p = {"oturum_id": str(oturum_id), **_ders_parametreleri(*yeni)}
    if sablon == tasindi:
        p |= eski_p
    await _telafi_kuyrugu(session, ogrenci_id, sablon, p, simdi)


async def telafi_kaldirildi(
    session: AsyncSession, ogrenci_id: uuid.UUID, oturum_id: uuid.UUID, tarih: date, baslangic: time, grup_ad: str,
    simdi: datetime, tur: str = "telafi",
) -> None:
    """Telafi/ek ders kaldırıldı. Planlandı bildirimi henüz gitmediyse ikisi de düşer (veli hiçbir şey görmez); taşındı
    bildirimi gitmediyse veli eski dersi bildiği için eski ders iptali gider."""
    gider: dict | None = {"oturum_id": str(oturum_id), **_ders_parametreleri(tarih, baslangic, grup_ad)}
    planlandi, _, iptal = PLAN_SABLONLARI[tur]
    for b in await _bekleyen_telafi(session, ogrenci_id, oturum_id, tur):
        b.durum = BildirimDurum.iptal
        if b.sablon == planlandi:
            gider = None if gider is not None and "eski" not in gider else gider
        else:
            p = b.parametreler or {}
            gider = {"oturum_id": str(oturum_id), "tarih": p["eski_tarih"], "baslangic": p["eski_baslangic"], "grup": p["eski_grup"], "eski": True}
    if gider is not None:
        gider.pop("eski", None)
        await _telafi_kuyrugu(session, ogrenci_id, iptal, gider, simdi)


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
    """Yoklamanın yeni durumuna göre `ders_gelmedi` kuyruğa alır (telafi ve ek derste devamsızlık bildirimi yoktur).
    Bakiye olayları, ders hakkı düşüldüğünde (geldi: hemen, gelmedi: 1 saat sonra işçide) ayrıca kontrol edilir."""
    if yoklama.telafi_mi or yoklama.ek_ders_mi:
        return
    if yoklama.durum.value == "gelmedi":
        oturum = await session.get(DersOturumu, yoklama.oturum_id)
        geri_alma, _ = await ayarlari_oku(session)
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
                "sebep": yoklama.sebep.value if yoklama.sebep else None,
            },
            bekleme=geri_alma,
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
    Bakiye tam eşiğe (varsayılan 2) eşitse `ders_hakki_azaldi`; 0 ya da altındaysa ve ödenmiş paketi varsa `ders_hakki_bitti`."""
    bakiye = await _normal_bakiye(session, ogrenci_id)
    _, esik = await ayarlari_oku(session)
    if bakiye == esik:
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


async def metin_olustur(session: AsyncSession, bildirim: Bildirim, *, soylenis: bool = False) -> str:
    """Bildirimin mesaj metnini kayıttan üretir (öğrencinin adı gönderim anında okunur).
    `soylenis=True`: kişisel şablonlarda bildirim kimliğine göre seçilen alternatif söyleniş (WhatsApp)."""
    sablon = soylenis_sec(bildirim.sablon, bildirim.id) if soylenis and bildirim.sablon in SOYLENISLER else SABLONLAR[bildirim.sablon]
    if bildirim.sablon == DUYURU:
        duyuru = await session.get(Duyuru, bildirim.duyuru_id) if bildirim.duyuru_id else None
        return duyuru.metin if duyuru is not None else ""
    ogrenci = await session.get(Ogrenci, bildirim.ogrenci_id)
    p = bildirim.parametreler or {}
    def _gun(anahtar: str) -> str:
        if not p.get(anahtar):
            return ""
        y, a, g = p[anahtar].split("-")
        return f"{g}.{a}.{y}"

    return sablon.format(
        ad=ogrenci.ad, tarih=_gun("tarih"), saat=p.get("baslangic", ""), bakiye=p.get("bakiye", 0),
        grup=p.get("grup", ""), eski_tarih=_gun("eski_tarih"), eski_saat=p.get("eski_baslangic", ""),
        eski_grup=p.get("eski_grup", ""), **gelmedi_alanlari(p.get("sebep")),
    ).replace("  ", " ")
