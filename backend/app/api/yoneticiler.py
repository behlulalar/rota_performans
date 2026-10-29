import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.api.antrenorler import (
    GIRIS_TEKRAR,
    _giris_hazirla,
    _oturumlari_iptal_et,
    _telefon_normalize,
    cakisma_denetle,
    gecici_sifre_uret,
)
from app.db import get_session
from app.deps import rol_gerekli
from app.models.kullanici import Kullanici, Rol
from app.schemas.antrenor import SifreSifirlaYanit
from app.schemas.yonetici import YoneticiGuncelle, YoneticiOlustur, YoneticiOlusturYanit, YoneticiOzet
from app.security import sifre_ozeti

router = APIRouter(prefix="/api/yoneticiler", tags=["yoneticiler"])

BULUNAMADI = "Yönetici bulunamadı"
SON_YONETICI = "Son aktif yönetici pasife alınamaz"
KENDINI_PASIFE_ALMA = "Kendi hesabınızı pasife alamazsınız"
KENDI_GIRISI = "Kendi giriş bilginizi Ayarlar > Hesabım bölümünden değiştirin"
KENDI_TELEFONU = "Kendi telefonunuzu Ayarlar > Hesabım bölümünden değiştirin"
KENDI_SIFRESI = "Kendi şifrenizi Ayarlar > Hesabım bölümünden değiştirin"

Yonetici = Depends(rol_gerekli(Rol.admin))


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _ozet(k: Kullanici, ben_id: uuid.UUID) -> YoneticiOzet:
    return YoneticiOzet(
        id=k.id, ad_soyad=k.ad_soyad, giris=k.giris, telefon=k.telefon, aktif=k.aktif, son_giris=k.son_giris,
        olusturma=k.olusturma, ben=k.id == ben_id,
    )


async def _yonetici_al(session: AsyncSession, yonetici_id: uuid.UUID) -> Kullanici:
    k = await session.get(Kullanici, yonetici_id)
    if k is None or k.rol != Rol.admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, BULUNAMADI)
    return k


@router.get("", response_model=list[YoneticiOzet])
async def listele(ben: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
    satirlar = await session.execute(
        select(Kullanici).where(Kullanici.rol == Rol.admin).order_by(Kullanici.ad_soyad, Kullanici.olusturma)
    )
    return [_ozet(k, ben.id) for k in satirlar.scalars()]


@router.post("", response_model=YoneticiOlusturYanit, status_code=status.HTTP_201_CREATED)
async def olustur(
    govde: YoneticiOlustur,
    request: Request,
    ben: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    giris = _giris_hazirla(govde.giris)
    if (await session.execute(select(Kullanici.id).where(Kullanici.giris == giris))).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
    await cakisma_denetle(session, giris)
    telefon = _telefon_normalize(govde.telefon) if govde.telefon else None
    if telefon == giris:
        telefon = None  # giriş zaten bu telefon
    if telefon is not None:
        await cakisma_denetle(session, telefon)
    sifre = gecici_sifre_uret()
    kullanici = Kullanici(
        rol=Rol.admin, giris=giris, telefon=telefon, sifre_ozeti=sifre_ozeti(sifre), ad_soyad=govde.ad_soyad, aktif=True,
        sifre_degistirmeli=True,
    )
    session.add(kullanici)
    await session.flush()
    await audit.kaydet(
        session, "yonetici_olusturuldu", kullanici_id=ben.id, hedef_tur="yonetici", hedef_id=str(kullanici.id),
        ip=_ip(request),
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
    await session.refresh(kullanici)
    return YoneticiOlusturYanit(yonetici=_ozet(kullanici, ben.id), gecici_sifre=sifre)


@router.patch("/{yonetici_id}", response_model=YoneticiOzet)
async def guncelle(
    yonetici_id: uuid.UUID,
    govde: YoneticiGuncelle,
    request: Request,
    ben: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    hedef = await _yonetici_al(session, yonetici_id)
    verilen = govde.model_fields_set
    for alan in ("ad_soyad", "giris", "aktif"):
        if alan in verilen and getattr(govde, alan) is None:
            raise HTTPException(422, f"{alan} boş olamaz")
    kendisi = hedef.id == ben.id
    oturumlar_kapansin = False

    if "aktif" in verilen and govde.aktif is False and hedef.aktif:
        diger = await session.scalar(
            select(func.count(Kullanici.id)).where(
                Kullanici.rol == Rol.admin, Kullanici.aktif.is_(True), Kullanici.id != hedef.id
            )
        )
        if not diger:
            raise HTTPException(status.HTTP_409_CONFLICT, SON_YONETICI)
        if kendisi:
            raise HTTPException(422, KENDINI_PASIFE_ALMA)

    if "giris" in verilen:
        giris = _giris_hazirla(govde.giris)
        if giris != hedef.giris:
            if kendisi:
                raise HTTPException(422, KENDI_GIRISI)
            if (await session.execute(select(Kullanici.id).where(Kullanici.giris == giris))).first() is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
            await cakisma_denetle(session, giris, hedef.id)
            hedef.giris = giris
            if hedef.telefon == giris:
                hedef.telefon = None
            oturumlar_kapansin = True
    if "telefon" in verilen:
        telefon = _telefon_normalize(govde.telefon) if govde.telefon else None
        if telefon == hedef.giris:
            telefon = None
        if telefon != hedef.telefon:
            if kendisi:
                raise HTTPException(422, KENDI_TELEFONU)
            if telefon is not None:
                await cakisma_denetle(session, telefon, hedef.id)
            hedef.telefon = telefon
            oturumlar_kapansin = True
    if "ad_soyad" in verilen:
        hedef.ad_soyad = govde.ad_soyad
    if "aktif" in verilen:
        if not govde.aktif and hedef.aktif:
            oturumlar_kapansin = True
        hedef.aktif = govde.aktif
    if oturumlar_kapansin:
        await _oturumlari_iptal_et(session, hedef.id)
    await audit.kaydet(
        session, "yonetici_guncellendi", kullanici_id=ben.id, hedef_tur="yonetici", hedef_id=str(hedef.id),
        ip=_ip(request), detay={"alanlar": sorted(verilen)},
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
    await session.refresh(hedef)
    return _ozet(hedef, ben.id)


@router.post("/{yonetici_id}/sifre-sifirla", response_model=SifreSifirlaYanit)
async def sifre_sifirla(
    yonetici_id: uuid.UUID,
    request: Request,
    ben: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    hedef = await _yonetici_al(session, yonetici_id)
    if hedef.id == ben.id:
        raise HTTPException(422, KENDI_SIFRESI)
    sifre = gecici_sifre_uret()
    hedef.sifre_ozeti = sifre_ozeti(sifre)
    hedef.sifre_degistirmeli = True
    hedef.basarisiz_deneme = 0
    hedef.kilit_bitis = None
    await _oturumlari_iptal_et(session, hedef.id)
    await audit.kaydet(
        session, "yonetici_sifre_sifirlandi", kullanici_id=ben.id, hedef_tur="yonetici", hedef_id=str(hedef.id),
        ip=_ip(request),
    )
    await session.commit()
    return SifreSifirlaYanit(gecici_sifre=sifre)
