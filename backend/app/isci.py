"""Arka plan işçisi: `python -m app.isci`.
Her 30 saniyede bekleyen devamsızlıkları işler, saatte bir ilerideki ders oturumlarını üretir,
günde bir (İstanbul takvim günü değişince ve açılışta) süresi dolan telafi haklarını düşer.
Günlüğe kişisel veri yazılmaz, yalnızca sayılar."""
import asyncio
import logging
import signal
import time
from datetime import timedelta

from redis.asyncio import Redis

from app import ders_hakki, push, whatsapp_gonder
from app.config import settings
from app.db import SessionLocal, engine
from app.oturumlar import URETIM_GUN, bugun, oturumlari_uret, simdi

log = logging.getLogger("isci")

DONGU_SANIYE = 30
URETIM_SANIYE = 3600
PUSH_PARTI = 50
WHATSAPP_PARTI = 50  # döngüde en çok 1 mesaj gider; bu, aday satır penceresidir
# Destek ekranı işçinin canlı olduğunu bu anahtardan (son atışın epoch saniyesi) anlar.
KALP_ATISI_ANAHTAR = "isci:kalp_atisi"
KALP_ATISI_TTL = 120


async def devamsizliklari_isle() -> None:
    async with SessionLocal() as session:
        sayi = await ders_hakki.bekleyen_devamsizliklari_isle(session, simdi())
        await session.commit()
    if sayi:
        log.info("%d yoklama için devamsızlık hareketi yazıldı", sayi)


async def suresi_dolan_telafileri_isle() -> None:
    # Tekrar çalışması ya da iki işçinin aynı anda çalışması güvenlidir (bkz. ders_hakki).
    sayi = await ders_hakki.suresi_dolan_telafileri_isle(SessionLocal, bugun(), simdi())
    if sayi:
        log.info("Süresi dolan %d telafi hakkı düşüldü", sayi)


async def push_bildirimlerini_gonder() -> None:
    async with SessionLocal() as session:
        await push.push_gonder(session, simdi(), limit=PUSH_PARTI)
        await session.commit()


async def whatsapp_bildirimlerini_gonder() -> None:
    async with SessionLocal() as session:
        await whatsapp_gonder.whatsapp_gonder(session, simdi(), limit=WHATSAPP_PARTI)
        await session.commit()


async def oturumlari_hazirla() -> None:
    async with SessionLocal() as session:
        bas = bugun()
        sayi = await oturumlari_uret(session, bas, bas + timedelta(days=URETIM_GUN))
        await session.commit()
    log.info("Oturum üretimi tamamlandı, yeni oturum: %d", sayi)


async def kalp_atisi_yaz() -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.set(KALP_ATISI_ANAHTAR, str(int(time.time())), ex=KALP_ATISI_TTL)
    finally:
        await redis.aclose()


async def calis(durdur: asyncio.Event) -> None:
    son_uretim: float | None = None
    son_telafi_gunu = None
    while not durdur.is_set():
        try:
            await kalp_atisi_yaz()
        except Exception:
            log.exception("Kalp atışı yazılamadı")
        try:
            await devamsizliklari_isle()
        except Exception:
            log.exception("Devamsızlık işleme başarısız")
        if son_telafi_gunu != bugun():
            try:
                gun = bugun()
                await suresi_dolan_telafileri_isle()
                son_telafi_gunu = gun
            except Exception:
                log.exception("Telafi süre dolumu başarısız")
        try:
            await push_bildirimlerini_gonder()
        except Exception:
            log.exception("Push gönderimi başarısız")
        try:
            await whatsapp_bildirimlerini_gonder()
        except Exception:
            log.exception("WhatsApp gönderimi başarısız")
        if son_uretim is None or time.monotonic() - son_uretim >= URETIM_SANIYE:
            try:
                await oturumlari_hazirla()
                son_uretim = time.monotonic()
            except Exception:
                log.exception("Oturum üretimi başarısız")
        try:
            await asyncio.wait_for(durdur.wait(), timeout=DONGU_SANIYE)
        except asyncio.TimeoutError:
            pass


async def ana() -> None:
    durdur = asyncio.Event()
    dongu = asyncio.get_running_loop()
    for sinyal in (signal.SIGTERM, signal.SIGINT):
        dongu.add_signal_handler(sinyal, durdur.set)
    log.info("İşçi başladı")
    try:
        await calis(durdur)
    finally:
        await engine.dispose()
        log.info("İşçi kapandı")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(ana())
