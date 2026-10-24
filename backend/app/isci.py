"""Arka plan işçisi: `python -m app.isci`.
Her 30 saniyede bekleyen devamsızlıkları işler, saatte bir ilerideki ders oturumlarını üretir.
Günlüğe kişisel veri yazılmaz, yalnızca sayılar."""
import asyncio
import logging
import signal
import time
from datetime import timedelta

from app import ders_hakki
from app.db import SessionLocal, engine
from app.oturumlar import bugun, oturumlari_uret, simdi

log = logging.getLogger("isci")

DONGU_SANIYE = 30
URETIM_SANIYE = 3600
URETIM_GUN = 14


async def devamsizliklari_isle() -> None:
    async with SessionLocal() as session:
        sayi = await ders_hakki.bekleyen_devamsizliklari_isle(session, simdi())
        await session.commit()
    if sayi:
        log.info("%d yoklama için devamsızlık hareketi yazıldı", sayi)


async def oturumlari_hazirla() -> None:
    async with SessionLocal() as session:
        bas = bugun()
        sayi = await oturumlari_uret(session, bas, bas + timedelta(days=URETIM_GUN))
        await session.commit()
    log.info("Oturum üretimi tamamlandı, yeni oturum: %d", sayi)


async def calis(durdur: asyncio.Event) -> None:
    son_uretim: float | None = None
    while not durdur.is_set():
        try:
            await devamsizliklari_isle()
        except Exception:
            log.exception("Devamsızlık işleme başarısız")
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
