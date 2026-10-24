import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kullanici import DenetimKaydi


async def kaydet(
    session: AsyncSession,
    islem: str,
    *,
    kullanici_id: uuid.UUID | None = None,
    hedef_tur: str | None = None,
    hedef_id: str | None = None,
    ip: str | None = None,
    detay: dict | None = None,
) -> None:
    """Denetim kaydı ekler. Çağıran commit eder. Detaya parola, belirteç ve kişisel veri yazılmaz."""
    session.add(
        DenetimKaydi(
            kullanici_id=kullanici_id,
            islem=islem,
            hedef_tur=hedef_tur,
            hedef_id=hedef_id,
            ip=ip,
            detay=detay,
        )
    )
