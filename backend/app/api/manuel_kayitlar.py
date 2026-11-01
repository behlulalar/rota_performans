"""Manuel gelir/gider kayıtları (gelir raporuna yansır). Liste yönetici ve teknik destek (tutarlar maskeli);
ekleme ve iptal yalnız yönetici."""
import calendar
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db import get_session
from app.deps import rol_gerekli, yalniz_yonetici
from app.maskele import tutar_gizle
from app.models.kullanici import Kullanici, Rol
from app.models.manuel_kayit import ManuelKayit
from app.oturumlar import bugun, simdi
from app.schemas.manuel_kayit import ManuelKayitGirdi, ManuelKayitIptal, ManuelKayitYanit

router = APIRouter(prefix="/api/manuel-kayitlar", tags=["manuel-kayitlar"])

Yonetici = Depends(rol_gerekli(Rol.admin))
FinansYazma = Depends(yalniz_yonetici)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _yanit(k: ManuelKayit, olusturan: str | None) -> ManuelKayitYanit:
    return ManuelKayitYanit(
        id=k.id, tur=k.tur, tutar=k.tutar, tarih=k.tarih, yontem=k.yontem, aciklama=k.aciklama,
        olusturan=olusturan, olusturma=k.olusturma, iptal=k.iptal_zamani is not None, iptal_nedeni=k.iptal_nedeni,
    )


async def _olusturan(session: AsyncSession, k: ManuelKayit) -> str | None:
    if k.olusturan_id is None:
        return None
    u = await session.get(Kullanici, k.olusturan_id)
    return (u.ad_soyad or u.giris) if u else None


@router.get("", response_model=list[ManuelKayitYanit])
async def listele(
    yil: int | None = Query(default=None, ge=2000, le=2100),
    ay: int | None = Query(default=None, ge=1, le=12),
    kullanici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    t = bugun()
    yil, ay = yil or t.year, ay or t.month
    bas, son = date(yil, ay, 1), date(yil, ay, calendar.monthrange(yil, ay)[1])
    satirlar = (
        await session.execute(
            select(ManuelKayit, Kullanici.ad_soyad, Kullanici.giris)
            .outerjoin(Kullanici, Kullanici.id == ManuelKayit.olusturan_id)
            .where(ManuelKayit.tarih >= bas, ManuelKayit.tarih <= son)
            .order_by(ManuelKayit.tarih.desc(), ManuelKayit.olusturma.desc())
        )
    ).all()
    return tutar_gizle(kullanici, [_yanit(k, ad or giris) for k, ad, giris in satirlar])


@router.post("", response_model=ManuelKayitYanit, status_code=201)
async def ekle(
    govde: ManuelKayitGirdi, request: Request, yonetici: Kullanici = FinansYazma,
    session: AsyncSession = Depends(get_session),
):
    if govde.tarih > bugun():
        raise HTTPException(422, "Tarih gelecekte olamaz")
    k = ManuelKayit(**govde.model_dump(), olusturan_id=yonetici.id)
    session.add(k)
    await session.flush()
    await audit.kaydet(
        session, f"manuel_{govde.tur.value}_eklendi", kullanici_id=yonetici.id, hedef_tur="manuel_kayit",
        hedef_id=str(k.id), ip=_ip(request),
        detay={"tutar": f"{govde.tutar:.2f}", "tarih": govde.tarih.isoformat(), "aciklama": govde.aciklama},
    )
    await session.commit()
    await session.refresh(k)
    return _yanit(k, yonetici.ad_soyad or yonetici.giris)


@router.post("/{kayit_id}/iptal", response_model=ManuelKayitYanit)
async def iptal(
    kayit_id: uuid.UUID, govde: ManuelKayitIptal, request: Request, yonetici: Kullanici = FinansYazma,
    session: AsyncSession = Depends(get_session),
):
    k = (await session.execute(select(ManuelKayit).where(ManuelKayit.id == kayit_id).with_for_update())).scalar_one_or_none()
    if k is None:
        raise HTTPException(404, "Kayıt bulunamadı")
    if k.iptal_zamani is not None:
        raise HTTPException(409, "Kayıt zaten iptal edilmiş")
    k.iptal_zamani, k.iptal_nedeni, k.iptal_eden_id = simdi(), govde.neden, yonetici.id
    await audit.kaydet(
        session, f"manuel_{k.tur.value}_iptal_edildi", kullanici_id=yonetici.id, hedef_tur="manuel_kayit",
        hedef_id=str(k.id), ip=_ip(request), detay={"tutar": f"{k.tutar:.2f}", "neden": govde.neden},
    )
    await session.commit()
    await session.refresh(k)
    return _yanit(k, await _olusturan(session, k))
