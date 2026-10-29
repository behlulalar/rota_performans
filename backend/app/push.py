"""Web Push gönderimi (VAPID). İşçi her döngüde `push_gonder` çağırır; çağıran commit eder.

Kararlar:
- VAPID ayarı yoksa hiçbir şey gönderilmez ve satırlara dokunulmaz (bekliyor kalır).
- Planlı zamanı 24 saatten eski satırlar gönderilmez, `iptal` + hata="süresi geçti" olur (eski devamsızlık bildirimi gitmesin).
- Alıcı hesabın hiç aboneliği yoksa satır `hata` ("abonelik yok") olur: cihaz sonradan açılınca eski bildirim gitmez.
- Push servisi 404/410 dönerse abonelik silinir. Diğer hatalarda 2^deneme dakika sonra yeniden denenir,
  MAKS_DENEME denemeden sonra `hata` olur. Günlüğe ve hata alanına kişisel veri yazılmaz."""
import asyncio
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import bildirim as bsvc
from app.config import settings
from app.models.bildirim import Bildirim, BildirimDurum, BildirimKanal, PushAbonelik
from app.models.ogrenci import IletisimKisisi

log = logging.getLogger("push")

MAKS_DENEME = 5
ESKI_SURE = timedelta(hours=24)
ZAMAN_ASIMI_SANIYE = 10
SERVIS_TTL = 6 * 3600  # push servisi cihaz kapalıysa en çok 6 saat bekletir
BASLIK = "Rota Performans"
_uyari_verildi = False


def _gonder_senkron(bilgi: dict, veri: str) -> int:
    """Tek aboneliğe gönderir (bloklayıcı). 0 = başarılı, aksi halde HTTP durumu; ağ hatasında -1."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=bilgi,
            data=veri,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            timeout=ZAMAN_ASIMI_SANIYE,
            ttl=SERVIS_TTL,
        )
        return 0
    except WebPushException as e:
        yanit = getattr(e, "response", None)
        return int(yanit.status_code) if yanit is not None else -1
    except Exception:
        return -1


async def _alicinin_abonelikleri(session: AsyncSession, bildirim: Bildirim) -> list[PushAbonelik] | None:
    kisi = await session.get(IletisimKisisi, bildirim.alici_iletisim_id)
    if kisi is None or kisi.kullanici_id is None:
        return None
    return list(
        (await session.execute(select(PushAbonelik).where(PushAbonelik.kullanici_id == kisi.kullanici_id))).scalars()
    )


async def push_gonder(session: AsyncSession, simdi: datetime, limit: int = 50) -> dict[str, int]:
    """Zamanı gelen push bildirimlerini gönderir; sayaçları verir."""
    global _uyari_verildi
    sayac = {"gonderildi": 0, "yeniden": 0, "hata": 0, "iptal": 0, "silinen_abonelik": 0}
    if not settings.push_etkin:
        if not _uyari_verildi:
            log.warning("VAPID ayarları eksik: push gönderimi kapalı, bildirimler bekletiliyor")
            _uyari_verildi = True
        return sayac
    for b in await bsvc.gonderilecekleri_al(session, simdi, limit, BildirimKanal.push):
        if b.planli_zaman < simdi - ESKI_SURE:
            b.durum, b.hata = BildirimDurum.iptal, "süresi geçti"
            sayac["iptal"] += 1
            continue
        abonelikler = await _alicinin_abonelikleri(session, b)
        if not abonelikler:
            b.durum, b.hata = BildirimDurum.hata, "abonelik yok"
            sayac["hata"] += 1
            continue
        veri = json.dumps(
            {
                "baslik": BASLIK,
                "govde": await bsvc.metin_olustur(session, b),
                # Duyuru çocuğa özel değildir (kardeşler tek bildirim alır): ana panele gider.
                "url": "/panel" if b.sablon == bsvc.DUYURU else f"/panel/cocuk/{b.ogrenci_id}",
                "etiket": f"bildirim-{b.id}",
            },
            ensure_ascii=False,
        )
        basarili, gecici_hata = 0, False
        for a in abonelikler:
            bilgi = {"endpoint": a.endpoint, "keys": {"p256dh": a.p256dh, "auth": a.auth}}
            kod = await asyncio.to_thread(_gonder_senkron, bilgi, veri)
            if kod == 0:
                basarili += 1
                a.son_kullanim = simdi
            elif kod in (404, 410):
                await session.delete(a)
                sayac["silinen_abonelik"] += 1
            else:
                gecici_hata = True
        if basarili:
            b.durum, b.gonderim_zamani, b.hata = BildirimDurum.gonderildi, simdi, None
            sayac["gonderildi"] += 1
        elif gecici_hata:
            b.deneme += 1
            if b.deneme >= MAKS_DENEME:
                b.durum, b.hata = BildirimDurum.hata, "push servisi hatası"
                sayac["hata"] += 1
            else:
                b.planli_zaman = simdi + timedelta(minutes=2**b.deneme)
                b.hata = "push servisi hatası"
                sayac["yeniden"] += 1
        else:  # tüm abonelikler geçersizdi ve silindi
            b.durum, b.hata = BildirimDurum.hata, "abonelik yok"
            sayac["hata"] += 1
    if any(sayac.values()):
        log.info("Push: %s", sayac)
    return sayac
