"""WhatsApp bağlantısı (yönetici ve teknik destek): durum, QR ile bağlama, bağlantıyı kesme."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app import whatsapp as wa
from app import whatsapp_gonder as wag
from app.db import get_session
from app.deps import rol_gerekli
from app.models.bildirim import Bildirim, BildirimDurum, BildirimKanal
from app.models.kullanici import Kullanici, Rol
from app.oturumlar import simdi
from app.ratelimit import get_redis

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

Yonetici = Depends(rol_gerekli(Rol.admin))


class DevreKesici(BaseModel):
    """Art arda hata ya da bağlantı kopması gönderimi durdurduysa açıktır (30 dk sonra kendiliğinden kapanır)."""

    acik: bool = False
    sebep: str | None = None


class BaglantiYaniti(BaseModel):
    durum: wa.Durum
    numara: str | None = None
    profil_adi: str | None = None
    qr: str | None = None
    devre_kesici: DevreKesici = DevreKesici()
    bekleyen_sayisi: int = 0  # kuyrukta bekleyen WhatsApp bildirimi


async def _yanit(b: wa.Baglanti, session: AsyncSession, redis: Redis) -> BaglantiYaniti:
    acik, sebep = await wag.devre_durumu(redis, simdi())
    bekleyen = (
        await session.execute(
            select(func.count()).where(Bildirim.kanal == BildirimKanal.whatsapp, Bildirim.durum == BildirimDurum.bekliyor)
        )
    ).scalar_one()
    return BaglantiYaniti(
        durum=b.durum, numara=b.numara, profil_adi=b.profil_adi, qr=b.qr,
        devre_kesici=DevreKesici(acik=acik, sebep=sebep), bekleyen_sayisi=bekleyen,
    )


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


@router.get("", response_model=BaglantiYaniti)
async def getir(
    _: Kullanici = Yonetici, session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)
):
    return await _yanit(await wa.durum(), session, redis)


@router.post("/baglan", response_model=BaglantiYaniti)
async def baglan(
    _: Kullanici = Yonetici, session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)
):
    """Yeni QR üretir (QR yaklaşık 40 sn geçerlidir; ekran süresi dolunca yeniden çağırır)."""
    try:
        return await _yanit(await wa.baglan(), session, redis)
    except wa.WhatsAppHatasi as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "WhatsApp servisine ulaşılamadı") from e


@router.post("/kes", response_model=BaglantiYaniti)
async def kes(
    request: Request,
    kullanici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    onceki = await wa.durum()
    if onceki.durum == "yapilandirilmadi":
        raise HTTPException(status.HTTP_409_CONFLICT, "WhatsApp yapılandırılmamış")
    try:
        await wa.baglantiyi_kes()
    except wa.WhatsAppHatasi as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "WhatsApp servisine ulaşılamadı") from e
    await audit.kaydet(
        session, "whatsapp_baglantisi_kesildi", kullanici_id=kullanici.id, hedef_tur="whatsapp", hedef_id=None,
        ip=_ip(request), detay={"numara": onceki.numara} if onceki.numara else None,
    )
    await session.commit()
    return await _yanit(await wa.durum(), session, redis)
