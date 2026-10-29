"""Denetim kaydı ekranı (yalnız yönetici, salt okunur). Bu ekranın görüntülenmesi denetim kaydı üretmez."""
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import rol_gerekli
from app.models.kullanici import DenetimKaydi, Kullanici, Rol
from app.schemas.denetim import DenetimKullanici, DenetimListe, DenetimSatiri

router = APIRouter(prefix="/api/denetim", tags=["denetim"])

Yonetici = Depends(rol_gerekli(Rol.admin))

_GIZLI_ANAHTARLAR = ("sifre", "token")


def _temizle(deger):
    """Detaydaki parola/belirteç benzeri anahtarları (iç içe olanlar dahil) savunma amaçlı atar."""
    if isinstance(deger, dict):
        return {k: _temizle(v) for k, v in deger.items() if not any(g in str(k).lower() for g in _GIZLI_ANAHTARLAR)}
    if isinstance(deger, list):
        return [_temizle(v) for v in deger]
    return deger


def _gun_basi(gun: date) -> datetime:
    return datetime.combine(gun, time.min, tzinfo=ZoneInfo(settings.saat_dilimi))


@router.get("/islemler", response_model=list[str])
async def islemler(_: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
    satirlar = await session.execute(select(DenetimKaydi.islem).distinct().order_by(DenetimKaydi.islem))
    return list(satirlar.scalars().all())


@router.get("", response_model=DenetimListe)
async def listele(
    islem: str | None = None,
    kullanici_id: uuid.UUID | None = None,
    baslangic: date | None = None,
    bitis: date | None = None,
    ara: str | None = Query(None, max_length=100),
    sayfa: int = Query(1, ge=1),
    boyut: int = Query(50, ge=1, le=100),
    _: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    kosullar = []
    if islem:
        kosullar.append(DenetimKaydi.islem == islem)
    if kullanici_id:
        kosullar.append(DenetimKaydi.kullanici_id == kullanici_id)
    if baslangic:
        kosullar.append(DenetimKaydi.zaman >= _gun_basi(baslangic))
    if bitis:
        kosullar.append(DenetimKaydi.zaman < _gun_basi(bitis + timedelta(days=1)))
    ara = (ara or "").strip()
    if ara:
        desen = "%" + ara.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        kosullar.append(
            or_(DenetimKaydi.hedef_id.ilike(desen, escape="\\"), Kullanici.giris.ilike(desen, escape="\\"))
        )

    temel = select(DenetimKaydi).outerjoin(Kullanici, Kullanici.id == DenetimKaydi.kullanici_id).where(*kosullar)
    toplam = (await session.execute(select(func.count()).select_from(temel.subquery()))).scalar_one()
    kayitlar = (
        await session.execute(
            temel.add_columns(Kullanici)
            .order_by(DenetimKaydi.zaman.desc(), DenetimKaydi.id.desc())
            .limit(boyut)
            .offset((sayfa - 1) * boyut)
        )
    ).all()
    items = [
        DenetimSatiri(
            id=d.id,
            zaman=d.zaman,
            kullanici=DenetimKullanici(id=k.id, giris=k.giris, ad_soyad=k.ad_soyad, rol=k.rol.value) if k else None,
            islem=d.islem,
            hedef_tur=d.hedef_tur,
            hedef_id=d.hedef_id,
            ip=d.ip,
            detay=_temizle(d.detay) if d.detay is not None else None,
        )
        for d, k in kayitlar
    ]
    return DenetimListe(items=items, toplam=toplam, sayfa=sayfa, boyut=boyut)
