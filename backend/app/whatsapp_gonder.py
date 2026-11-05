"""WhatsApp gönderimi (Evolution API) ve ban koruması. İşçi her döngüde (30 sn) `whatsapp_gonder` çağırır.
Kurallar docs/bildirim-kurallari.md bölüm 4'tedir; özet:

- Yalnız kanal=whatsapp, durum=bekliyor, zamanı gelmiş satırlar. WhatsApp yapılandırılmamışsa ya da bağlantı
  `bagli` değilse hiçbir satıra dokunulmaz (bekler). Planlı zamanı 24 saatten eski satır `iptal` ("süresi geçti").
- Gönderim yalnız ayardaki pencerede (varsayılan 09:00–21:00, İstanbul); dışında satırlar bekler.
- Döngü başına EN FAZLA 1 mesaj; iki gönderim arasında rastgele 25–70 sn (Redis'te tutulur).
- Saatlik / günlük üst sınır (ayar) ve yeni numara için ısınma takvimi (günlük sınır = min(ayar, ısınma)).
- Kişisel bildirimler duyurulardan önce gider.
- Push-varsa-atla: alıcı push ile ulaşıyorsa WhatsApp satırı iptal edilir (ayar + duyuruda `her_iki_kanal` istisnası).
- Devre kesici: art arda 3 hata ya da bağlantı kopması -> Redis'te "açık" bayrağı (30 dk), gönderim durur.
- Hiçbir mesaj iki kez gitmez: gönderimden ÖNCE satır "hata / sonuç belirsiz" olarak commit edilir, sonuç sonra yazılır.
  Çökme ya da zaman aşımı gibi belirsiz durumlarda satır böyle kalır ve yeniden denenmez.
Bu modül her mesajdan sonra commit eder. Günlüğe ve hata alanına kişisel veri (telefon, ad, metin) yazılmaz."""
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import bildirim as bsvc
from app import whatsapp as wa
from app.config import settings
from app.models.ayarlar import KulupAyari
from app.models.bildirim import Bildirim, BildirimDurum, BildirimKanal, PushAbonelik
from app.models.duyuru import Duyuru
from app.models.ogrenci import IletisimKisisi

log = logging.getLogger("whatsapp_gonder")

MAKS_DENEME = 5
ESKI_SURE = timedelta(hours=24)
PUSH_GECERLILIK = timedelta(days=30)  # "push ile ulaşıyor" sayılmak için son başarılı push bu kadar yeni olmalı
ARALIK_SN = (25, 70)  # iki gönderim arası rastgele bekleme
YAZIYOR_MS = (1500, 4000)  # karşı tarafta "yazıyor…" süresi
DEVRE_SURESI = timedelta(minutes=30)
DEVRE_ESIGI = 3  # art arda bu kadar hata -> devre kesici açılır
BELIRSIZ_HATA = "gönderim sonucu belirsiz"

# Ayar satırı yoksa geçerli varsayılanlar (kulup_ayari sütun varsayılanlarıyla aynı).
VARSAYILAN_SAATLIK = 50
VARSAYILAN_GUNLUK = 250
VARSAYILAN_BASLANGIC = 9
VARSAYILAN_BITIS = 21

# Redis anahtarları
SONRAKI_ANAHTAR = "wa:sonraki_gonderim"  # bir sonraki mesajın en erken epoch saniyesi
HATA_SAYACI_ANAHTAR = "wa:art_arda_hata"
DEVRE_ANAHTAR = "wa:devre_kesici"  # JSON {"sebep": str, "bitis": epoch}


@dataclass
class Ayarlar:
    saatlik: int = VARSAYILAN_SAATLIK
    gunluk: int = VARSAYILAN_GUNLUK
    baslangic: int = VARSAYILAN_BASLANGIC
    bitis: int = VARSAYILAN_BITIS
    push_varsa_atla: bool = True


async def ayarlari_oku(session: AsyncSession) -> Ayarlar:
    a = await session.get(KulupAyari, 1)
    if a is None:
        return Ayarlar()
    return Ayarlar(a.wa_saatlik_limit, a.wa_gunluk_limit, a.wa_baslangic_saat, a.wa_bitis_saat, a.wa_push_varsa_atla)


def isinma_limiti(gun_no: int) -> int | None:
    """Numaranın ilk gönderiminden itibaren geçen güne göre günlük sınır (gün 1 = ilk gönderim günü).
    15. günden sonra ısınma sınırı yoktur (None): yalnız ayardaki limit geçerlidir."""
    if gun_no <= 3:
        return 20
    if gun_no <= 7:
        return 50
    if gun_no <= 14:
        return 120
    return None


# ---------- devre kesici (Redis) ----------


async def devre_durumu(redis: Redis, simdi: datetime) -> tuple[bool, str | None]:
    """(açık mı, sebep). Süresi dolmuş bayrak kapalı sayılır."""
    ham = await redis.get(DEVRE_ANAHTAR)
    if not ham:
        return False, None
    try:
        v = json.loads(ham)
        if float(v["bitis"]) <= simdi.timestamp():
            return False, None
        return True, str(v.get("sebep") or "bilinmiyor")
    except (ValueError, KeyError, TypeError):
        return False, None


async def _devre_ac(redis: Redis, simdi: datetime, sebep: str) -> None:
    """Zaten açıksa süreyi ve ilk sebebi korur."""
    acik, _ = await devre_durumu(redis, simdi)
    if acik:
        return
    bitis = simdi + DEVRE_SURESI
    await redis.set(DEVRE_ANAHTAR, json.dumps({"sebep": sebep, "bitis": bitis.timestamp()}), ex=int(DEVRE_SURESI.total_seconds()))
    await redis.delete(HATA_SAYACI_ANAHTAR)  # kapandıktan sonra sayaç sıfırdan başlar
    log.warning("WhatsApp devre kesici açıldı: %s", sebep)


async def _devre_kapat(redis: Redis) -> None:
    await redis.delete(DEVRE_ANAHTAR, HATA_SAYACI_ANAHTAR)


async def _hata_say(redis: Redis, simdi: datetime, sebep: str) -> None:
    n = await redis.incr(HATA_SAYACI_ANAHTAR)
    await redis.expire(HATA_SAYACI_ANAHTAR, 3600)
    if n >= DEVRE_ESIGI:
        await _devre_ac(redis, simdi, sebep)


# ---------- sayımlar ve kurallar ----------


def _gonderilmis():
    """Gönderilmiş (ya da gönderilmiş olabilecek: belirsiz) WhatsApp satırları."""
    return (
        Bildirim.kanal == BildirimKanal.whatsapp,
        Bildirim.gonderim_zamani.is_not(None),
        Bildirim.durum.in_([BildirimDurum.gonderildi, BildirimDurum.hata]),
    )


async def _limit_asildi(session: AsyncSession, simdi: datetime, ayar: Ayarlar) -> bool:
    tz = ZoneInfo(settings.saat_dilimi)
    yerel = simdi.astimezone(tz)
    gun_basi = datetime.combine(yerel.date(), datetime.min.time(), tzinfo=tz)
    saatlik = (
        await session.execute(
            select(func.count()).where(*_gonderilmis(), Bildirim.gonderim_zamani > simdi - timedelta(hours=1))
        )
    ).scalar_one()
    if saatlik >= ayar.saatlik:
        return True
    gunluk = (await session.execute(select(func.count()).where(*_gonderilmis(), Bildirim.gonderim_zamani >= gun_basi))).scalar_one()
    ilk = (await session.execute(select(func.min(Bildirim.gonderim_zamani)).where(*_gonderilmis()))).scalar_one()
    sinir = ayar.gunluk
    if ilk is not None:
        gun_no = (yerel.date() - ilk.astimezone(tz).date()).days + 1
        isinma = isinma_limiti(gun_no)
        if isinma is not None:
            sinir = min(sinir, isinma)
    return gunluk >= sinir


async def _push_ile_ulasiyor(session: AsyncSession, b: Bildirim, kisi: IletisimKisisi, simdi: datetime, duyuru: Duyuru | None) -> bool:
    """Alıcı bu bildirimi zaten push ile alıyor / aldı mı? Üç şart birlikte:
    1) hesabı var ve son 30 günde başarılı push almış (son_kullanim dolu) bir cihazı var,
    2) duyuruysa: duyuru push kanalında da gönderiliyor ve `her_iki_kanal` kapalı,
    3) aynı bildirimin push satırı bu alıcı için gerçekten var ve iptal/hata değil (veli push'u kapattıysa
       ya da push başarısızsa WhatsApp'a yine de gönderilir; aksi halde mesaj hiç ulaşmazdı)."""
    if kisi.kullanici_id is None:
        return False
    if duyuru is not None and (duyuru.her_iki_kanal or not duyuru.kanal_push):
        return False
    cihaz = (
        await session.execute(
            select(PushAbonelik.id)
            .where(PushAbonelik.kullanici_id == kisi.kullanici_id, PushAbonelik.son_kullanim >= simdi - PUSH_GECERLILIK)
            .limit(1)
        )
    ).first()
    if cihaz is None:
        return False
    kardes = select(Bildirim.id).where(
        Bildirim.kanal == BildirimKanal.push,
        Bildirim.alici_iletisim_id == b.alici_iletisim_id,
        Bildirim.sablon == b.sablon,
        Bildirim.durum.in_([BildirimDurum.bekliyor, BildirimDurum.gonderildi]),
    )
    if b.duyuru_id is not None:
        kardes = kardes.where(Bildirim.duyuru_id == b.duyuru_id)
    elif b.yoklama_id is not None:
        kardes = kardes.where(Bildirim.yoklama_id == b.yoklama_id)
    else:
        kardes = kardes.where(Bildirim.ogrenci_id == b.ogrenci_id, Bildirim.olusturma <= b.olusturma + timedelta(minutes=1))
    return (await session.execute(kardes.limit(1))).first() is not None


def _kisiye_gore_sirala():
    # Kişisel bildirimler (duyuru olmayanlar) duyurulardan önce.
    return case((Bildirim.sablon == bsvc.DUYURU, 1), else_=0)


async def whatsapp_gonder(
    session: AsyncSession,
    simdi: datetime,
    limit: int = 50,
    *,
    redis: Redis | None = None,
    rastgele: Callable[[int, int], int] = random.randint,
) -> dict[str, int]:
    """Bir döngüde en fazla BİR WhatsApp mesajı gönderir; sayaçları verir. `rastgele(alt, ust)`: bekleme ve
    "yazıyor…" süreleri için rastgele kaynağı (testte sabitlenir)."""
    sayac = {"gonderildi": 0, "yeniden": 0, "hata": 0, "iptal": 0}
    if not settings.whatsapp_etkin:
        return sayac
    # Zamanı gelmiş satır yoksa Evolution'a hiç gitmeden çık.
    var = (
        await session.execute(
            select(Bildirim.id)
            .where(Bildirim.kanal == BildirimKanal.whatsapp, Bildirim.durum == BildirimDurum.bekliyor, Bildirim.planli_zaman <= simdi)
            .limit(1)
        )
    ).first()
    if var is None:
        return sayac
    kapat = redis is None
    if redis is None:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await _dongu(session, simdi, limit, redis, rastgele, sayac)
    finally:
        if kapat:
            await redis.aclose()
    if any(sayac.values()):
        log.info("WhatsApp: %s", sayac)
    return sayac


async def _dongu(
    session: AsyncSession, simdi: datetime, limit: int, redis: Redis, rastgele: Callable[[int, int], int],
    sayac: dict[str, int],
) -> None:
    baglanti = await wa.durum()
    if baglanti.durum != "bagli":
        # Satırlara dokunulmaz, bağlanınca devam eder. Kopma/ulaşılamama devre kesiciyi de açar (yönetici uyarısı).
        if baglanti.durum in ("bagli_degil", "ulasilamiyor"):
            await _devre_ac(redis, simdi, "bağlantı koptu" if baglanti.durum == "bagli_degil" else "servise ulaşılamıyor")
        return

    # 24 saatten eski bekleyenler gönderilmez (devre kesici ve pencereden bağımsız).
    iptal = await session.execute(
        update(Bildirim)
        .where(
            Bildirim.kanal == BildirimKanal.whatsapp,
            Bildirim.durum == BildirimDurum.bekliyor,
            Bildirim.planli_zaman < simdi - ESKI_SURE,
        )
        .values(durum=BildirimDurum.iptal, hata="süresi geçti")
    )
    sayac["iptal"] += iptal.rowcount
    await session.commit()

    acik, _ = await devre_durumu(redis, simdi)
    if acik:
        return
    if await redis.exists(DEVRE_ANAHTAR):
        # Süre doldu ve bağlantı `bagli`: devre kesici kapanır.
        await _devre_kapat(redis)

    ayar = await ayarlari_oku(session)
    saat = simdi.astimezone(ZoneInfo(settings.saat_dilimi)).hour
    if not (ayar.baslangic <= saat < ayar.bitis):
        return
    sonraki = await redis.get(SONRAKI_ANAHTAR)
    if sonraki and float(sonraki) > simdi.timestamp():
        return
    if await _limit_asildi(session, simdi, ayar):
        return

    adaylar = list(
        (
            await session.execute(
                select(Bildirim)
                .where(
                    Bildirim.kanal == BildirimKanal.whatsapp,
                    Bildirim.durum == BildirimDurum.bekliyor,
                    Bildirim.planli_zaman <= simdi,
                )
                .order_by(_kisiye_gore_sirala(), Bildirim.planli_zaman, Bildirim.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars()
    )
    for b in adaylar:
        kisi = await session.get(IletisimKisisi, b.alici_iletisim_id)
        if kisi is None or not kisi.telefon:
            b.durum, b.hata = BildirimDurum.hata, "telefon yok"
            sayac["hata"] += 1
            continue
        duyuru = await session.get(Duyuru, b.duyuru_id) if b.duyuru_id else None
        if ayar.push_varsa_atla and await _push_ile_ulasiyor(session, b, kisi, simdi, duyuru):
            b.durum, b.hata = BildirimDurum.iptal, "push ile ulaşıyor"
            sayac["iptal"] += 1
            continue
        metin = await bsvc.metin_olustur(session, b, soylenis=True)
        if not metin.strip():
            b.durum, b.hata = BildirimDurum.hata, "mesaj metni yok"
            sayac["hata"] += 1
            continue
        await _gonder(session, redis, simdi, b, kisi.telefon, metin, rastgele, sayac)
        return  # döngü başına en fazla bir mesaj
    await session.commit()


async def _gonder(
    session: AsyncSession, redis: Redis, simdi: datetime, b: Bildirim, telefon: str, metin: str,
    rastgele: Callable[[int, int], int], sayac: dict[str, int],
) -> None:
    # Gönderimden ÖNCE "sonuç belirsiz" olarak kalıcı yaz: gönderim sırasında çökme olursa mesaj tekrar gitmez.
    b.durum, b.hata, b.gonderim_zamani = BildirimDurum.hata, BELIRSIZ_HATA, simdi
    await session.commit()
    # Sonraki mesaj için yeni rastgele aralık: sonuç ne olursa olsun (hatalı denemeler de hız sınırına tabidir).
    await redis.set(SONRAKI_ANAHTAR, str(simdi.timestamp() + rastgele(*ARALIK_SN)), ex=3600)
    try:
        await wa.metin_gonder(telefon, metin, rastgele(*YAZIYOR_MS))
    except wa.KesinHata:
        b.gonderim_zamani = None
        b.deneme += 1
        if b.deneme >= MAKS_DENEME:
            b.durum, b.hata = BildirimDurum.hata, "WhatsApp servisi hatası"
            sayac["hata"] += 1
        else:
            b.durum, b.hata = BildirimDurum.bekliyor, "WhatsApp servisi hatası"
            b.planli_zaman = simdi + timedelta(minutes=2**b.deneme)
            sayac["yeniden"] += 1
        await session.commit()
        await _hata_say(redis, simdi, "WhatsApp servisi hatası")
    except wa.GecersizNumara:
        b.durum, b.hata, b.gonderim_zamani = BildirimDurum.hata, "numara WhatsApp'ta yok", None
        sayac["hata"] += 1
        await session.commit()
    except wa.WhatsAppHatasi:  # BelirsizSonuc: mesaj gitmiş olabilir, durum "hata / belirsiz" kalır, yeniden denenmez
        sayac["hata"] += 1
        await _hata_say(redis, simdi, BELIRSIZ_HATA)
    except Exception:
        # Beklenmeyen hata: gönderilip gönderilmediği bilinmiyor, belirsiz kalır.
        sayac["hata"] += 1
        log.exception("WhatsApp gönderiminde beklenmeyen hata")
        await _hata_say(redis, simdi, BELIRSIZ_HATA)
    else:
        b.durum, b.hata = BildirimDurum.gonderildi, None
        sayac["gonderildi"] += 1
        await session.commit()
        await redis.delete(HATA_SAYACI_ANAHTAR)
