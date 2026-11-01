"""WhatsApp bağlantısı (yönetici ve teknik destek): durum, QR ile bağlama, bağlantıyı kesme."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app import whatsapp as wa
from app.db import get_session
from app.deps import rol_gerekli
from app.models.kullanici import Kullanici, Rol

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

Yonetici = Depends(rol_gerekli(Rol.admin))


class BaglantiYaniti(BaseModel):
    durum: wa.Durum
    numara: str | None = None
    profil_adi: str | None = None
    qr: str | None = None


def _yanit(b: wa.Baglanti) -> BaglantiYaniti:
    return BaglantiYaniti(durum=b.durum, numara=b.numara, profil_adi=b.profil_adi, qr=b.qr)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


@router.get("", response_model=BaglantiYaniti)
async def getir(_: Kullanici = Yonetici):
    return _yanit(await wa.durum())


@router.post("/baglan", response_model=BaglantiYaniti)
async def baglan(_: Kullanici = Yonetici):
    """Yeni QR üretir (QR yaklaşık 40 sn geçerlidir; ekran süresi dolunca yeniden çağırır)."""
    try:
        return _yanit(await wa.baglan())
    except wa.WhatsAppHatasi as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "WhatsApp servisine ulaşılamadı") from e


@router.post("/kes", response_model=BaglantiYaniti)
async def kes(request: Request, kullanici: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
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
    return _yanit(await wa.durum())
