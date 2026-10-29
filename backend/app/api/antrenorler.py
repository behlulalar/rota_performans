import secrets
import uuid

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app import telefon as telefon_modulu
from app.db import get_session
from app.deps import rol_gerekli
from app.models.kullanici import Kullanici, Oturum, Rol
from app.models.program import Antrenor, Grup
from app.schemas.antrenor import (
    AntrenorGuncelle,
    AntrenorOlustur,
    AntrenorOlusturYanit,
    AntrenorOzet,
    SifreSifirlaYanit,
)
from app.security import normalize_giris, sifre_ozeti

router = APIRouter(prefix="/api/antrenorler", tags=["antrenorler"])

GIRIS_TEKRAR = "Bu giriş bilgisi başka bir hesapta kayıtlı"
TELEFON_TEKRAR = "Bu telefon/giriş bilgisi başka bir hesapta kayıtlı"
BULUNAMADI = "Antrenör bulunamadı"

# Karıştırılabilen 0/O/l/1/I karakterleri yok.
_HARFLER = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_RAKAMLAR = "23456789"
SIFRE_UZUNLUK = 14

Yonetici = Depends(rol_gerekli(Rol.admin))


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _hata422(mesaj: str) -> HTTPException:
    return HTTPException(422, mesaj)


def _telefon_normalize(telefon: str) -> str:
    try:
        return telefon_modulu.normalize(telefon)
    except ValueError as hata:
        raise _hata422(str(hata))


def _giris_hazirla(giris: str) -> str:
    if "@" in giris:
        try:
            sonuc = validate_email(giris, check_deliverability=False)
        except EmailNotValidError:
            raise _hata422("Geçersiz e-posta adresi")
        return normalize_giris(sonuc.normalized)
    return normalize_giris(_telefon_normalize(giris))


async def cakisma_denetle(session: AsyncSession, deger: str, haric_id: uuid.UUID | None = None) -> None:
    """Giriş veya telefon olarak kullanılacak değer, başka bir hesabın giris ya da telefon alanında varsa 409.

    Giriş (giris) ile yönetici telefonu (telefon) aynı kimlik alanını paylaşır: biri diğerinin değeriyle çakışamaz.
    """
    sorgu = select(Kullanici.id).where((Kullanici.giris == deger) | (Kullanici.telefon == deger))
    if haric_id is not None:
        sorgu = sorgu.where(Kullanici.id != haric_id)
    if (await session.execute(sorgu.limit(1))).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, TELEFON_TEKRAR)


def gecici_sifre_uret() -> str:
    """En az bir harf ve bir rakam içeren, rastgele geçici şifre."""
    tum = _HARFLER + _RAKAMLAR
    while True:
        sifre = "".join(secrets.choice(tum) for _ in range(SIFRE_UZUNLUK))
        if any(c in _HARFLER for c in sifre) and any(c in _RAKAMLAR for c in sifre):
            return sifre


async def _ozetler(session: AsyncSession, kosullar: list) -> list[AntrenorOzet]:
    grup_sayisi = (
        select(func.count(Grup.id))
        .where(Grup.antrenor_id == Antrenor.id, Grup.aktif.is_(True))
        .correlate(Antrenor)
        .scalar_subquery()
    )
    satirlar = await session.execute(
        select(Antrenor, Kullanici.giris, grup_sayisi)
        .outerjoin(Kullanici, Kullanici.id == Antrenor.kullanici_id)
        .where(*kosullar)
        .order_by(Antrenor.ad_soyad, Antrenor.id)
    )
    return [
        AntrenorOzet(
            id=a.id, ad_soyad=a.ad_soyad, telefon=a.telefon, aktif=a.aktif, giris=giris, grup_sayisi=sayi
        )
        for a, giris, sayi in satirlar.all()
    ]


async def _ozet(session: AsyncSession, antrenor_id: uuid.UUID) -> AntrenorOzet:
    return (await _ozetler(session, [Antrenor.id == antrenor_id]))[0]


async def _antrenor_al(session: AsyncSession, antrenor_id: uuid.UUID) -> Antrenor:
    antrenor = await session.get(Antrenor, antrenor_id)
    if antrenor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, BULUNAMADI)
    return antrenor


@router.get("", response_model=list[AntrenorOzet])
async def listele(
    aktif: bool | None = Query(default=None),
    _: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    kosullar = [] if aktif is None else [Antrenor.aktif.is_(aktif)]
    return await _ozetler(session, kosullar)


@router.post("", response_model=AntrenorOlusturYanit, status_code=status.HTTP_201_CREATED)
async def olustur(
    govde: AntrenorOlustur,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    giris = _giris_hazirla(govde.giris)
    telefon = _telefon_normalize(govde.telefon) if govde.telefon else None
    if (await session.execute(select(Kullanici.id).where(Kullanici.giris == giris))).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
    await cakisma_denetle(session, giris)

    sifre = gecici_sifre_uret()
    kullanici = Kullanici(
        rol=Rol.antrenor, giris=giris, sifre_ozeti=sifre_ozeti(sifre), ad_soyad=govde.ad_soyad, aktif=True,
        sifre_degistirmeli=True,
    )
    session.add(kullanici)
    await session.flush()
    antrenor = Antrenor(kullanici_id=kullanici.id, ad_soyad=govde.ad_soyad, telefon=telefon, aktif=True)
    session.add(antrenor)
    await session.flush()
    await audit.kaydet(
        session, "antrenor_olusturuldu", kullanici_id=yonetici.id, hedef_tur="antrenor", hedef_id=str(antrenor.id),
        ip=_ip(request),
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
    return AntrenorOlusturYanit(antrenor=await _ozet(session, antrenor.id), gecici_sifre=sifre)


async def _oturumlari_iptal_et(session: AsyncSession, kullanici_id: uuid.UUID) -> None:
    await session.execute(update(Oturum).where(Oturum.kullanici_id == kullanici_id).values(iptal=True))


@router.patch("/{antrenor_id}", response_model=AntrenorOzet)
async def guncelle(
    antrenor_id: uuid.UUID,
    govde: AntrenorGuncelle,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    antrenor = await _antrenor_al(session, antrenor_id)
    verilen = govde.model_fields_set
    for alan in ("ad_soyad", "aktif"):
        if alan in verilen and getattr(govde, alan) is None:
            raise _hata422(f"{alan} boş olamaz")
    kullanici = await session.get(Kullanici, antrenor.kullanici_id) if antrenor.kullanici_id else None

    if "ad_soyad" in verilen:
        antrenor.ad_soyad = govde.ad_soyad
        if kullanici is not None:
            kullanici.ad_soyad = govde.ad_soyad
    if "giris" in verilen:
        if govde.giris is None:
            raise _hata422("giris boş olamaz")
        if kullanici is None:
            raise _hata422("Antrenörün giriş hesabı yok")
        giris = _giris_hazirla(govde.giris)
        if giris != kullanici.giris:
            if (await session.execute(select(Kullanici.id).where(Kullanici.giris == giris))).first() is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
            await cakisma_denetle(session, giris, kullanici.id)
            kullanici.giris = giris
            await _oturumlari_iptal_et(session, kullanici.id)
    if "telefon" in verilen:
        antrenor.telefon = _telefon_normalize(govde.telefon) if govde.telefon else None
    if "aktif" in verilen:
        antrenor.aktif = govde.aktif
        if kullanici is not None:
            kullanici.aktif = govde.aktif
            if not govde.aktif:
                await _oturumlari_iptal_et(session, kullanici.id)
    await audit.kaydet(
        session, "antrenor_guncellendi", kullanici_id=yonetici.id, hedef_tur="antrenor", hedef_id=str(antrenor.id),
        ip=_ip(request), detay={"alanlar": sorted(verilen)},
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
    return await _ozet(session, antrenor.id)


@router.post("/{antrenor_id}/sifre-sifirla", response_model=SifreSifirlaYanit)
async def sifre_sifirla(
    antrenor_id: uuid.UUID,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    antrenor = await _antrenor_al(session, antrenor_id)
    kullanici = await session.get(Kullanici, antrenor.kullanici_id) if antrenor.kullanici_id else None
    if kullanici is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Antrenörün giriş hesabı yok")
    sifre = gecici_sifre_uret()
    kullanici.sifre_ozeti = sifre_ozeti(sifre)
    kullanici.sifre_degistirmeli = True
    kullanici.basarisiz_deneme = 0
    kullanici.kilit_bitis = None
    await _oturumlari_iptal_et(session, kullanici.id)
    await audit.kaydet(
        session, "antrenor_sifre_sifirlandi", kullanici_id=yonetici.id, hedef_tur="antrenor",
        hedef_id=str(antrenor.id), ip=_ip(request),
    )
    await session.commit()
    return SifreSifirlaYanit(gecici_sifre=sifre)
