import asyncio
import secrets
import uuid
from datetime import datetime, timezone

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app import telefon as telefon_modulu
from app.db import get_session
from app.depolama import depolama
from app.deps import rol_gerekli
from app.foto import FOTO_EN_COK_BAYT, foto_isle
from app.models.kullanici import Kullanici, Oturum, Rol
from app.models.program import Antrenor, AntrenorFotoRizasi, Grup
from app.schemas.ogrenci import FotoBoyut
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
# Fotoğrafı giriş yapmış her aktif kullanıcı görür.
Goruntuleyen = Depends(rol_gerekli(Rol.admin, Rol.antrenor, Rol.veli, Rol.ogrenci))


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
    satirlar = satirlar.all()
    gruplar: dict[uuid.UUID, list[uuid.UUID]] = {}
    if satirlar:
        for aid, gid in await session.execute(
            select(Grup.antrenor_id, Grup.id)
            .where(Grup.antrenor_id.in_([a.id for a, _, _ in satirlar]), Grup.aktif.is_(True))
            .order_by(Grup.ad, Grup.id)
        ):
            gruplar.setdefault(aid, []).append(gid)
    rizalar: dict[uuid.UUID, datetime] = {}
    if satirlar:
        rizalar = dict(
            (await session.execute(
                select(AntrenorFotoRizasi.antrenor_id, AntrenorFotoRizasi.verildi).where(
                    AntrenorFotoRizasi.antrenor_id.in_([a.id for a, _, _ in satirlar]),
                    AntrenorFotoRizasi.geri_cekildi.is_(None),
                )
            )).all()
        )
    return [
        AntrenorOzet(
            id=a.id, ad_soyad=a.ad_soyad, telefon=a.telefon, aktif=a.aktif, giris=giris, grup_sayisi=sayi,
            foto_var=a.foto_anahtar is not None, foto_rizasi=rizalar.get(a.id),
            grup_idleri=gruplar.get(a.id, []),
        )
        for a, giris, sayi in satirlar
    ]


async def _ozet(session: AsyncSession, antrenor_id: uuid.UUID) -> AntrenorOzet:
    return (await _ozetler(session, [Antrenor.id == antrenor_id]))[0]


async def _antrenor_al(session: AsyncSession, antrenor_id: uuid.UUID) -> Antrenor:
    antrenor = await session.get(Antrenor, antrenor_id)
    if antrenor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, BULUNAMADI)
    return antrenor


async def _gruplari_ata(
    session: AsyncSession, antrenor_id: uuid.UUID, grup_idleri: list[uuid.UUID]
) -> dict[str, list[str]]:
    """Antrenörün aktif grupları tam olarak grup_idleri olur; diğerlerinin antrenörü boşalır (aynı işlem)."""
    istenen = set(grup_idleri)
    # Tüm ilgili satırlar TEK sorguda, id sırasıyla kilitlenir: eşzamanlı atamalar ters sırada kilitleyip kilitlenmez.
    kosul = and_(Grup.antrenor_id == antrenor_id, Grup.aktif.is_(True))
    if istenen:
        kosul = or_(Grup.id.in_(istenen), kosul)
    satirlar = {
        g.id: g
        for g in (await session.execute(select(Grup).where(kosul).order_by(Grup.id).with_for_update())).scalars()
    }
    if any(gid not in satirlar or not satirlar[gid].aktif for gid in istenen):
        raise _hata422("Grup bulunamadı veya pasif")
    mevcut = {gid: g for gid, g in satirlar.items() if g.antrenor_id == antrenor_id and g.aktif}
    eklenen = [gid for gid in sorted(istenen, key=str) if gid not in mevcut]
    cikarilan = [gid for gid in sorted(mevcut, key=str) if gid not in istenen]
    onceki = {str(gid): str(satirlar[gid].antrenor_id) for gid in eklenen if satirlar[gid].antrenor_id is not None}
    for gid in eklenen:
        satirlar[gid].antrenor_id = antrenor_id
    for gid in cikarilan:
        mevcut[gid].antrenor_id = None
    sonuc: dict = {"eklenen": [str(g) for g in eklenen], "cikarilan": [str(g) for g in cikarilan]}
    if onceki:
        sonuc["onceki_antrenor"] = onceki
    return sonuc


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
    telefon = _telefon_normalize(govde.telefon)
    giris = normalize_giris(telefon)
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
    detay = None
    if govde.grup_idleri:
        detay = {"gruplar": await _gruplari_ata(session, antrenor.id, govde.grup_idleri)}
    await audit.kaydet(
        session, "antrenor_olusturuldu", kullanici_id=yonetici.id, hedef_tur="antrenor", hedef_id=str(antrenor.id),
        ip=_ip(request), detay=detay,
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

    degisen: list[str] = []
    giris_degisti = False
    if "ad_soyad" in verilen:
        if govde.ad_soyad != antrenor.ad_soyad:
            degisen.append("ad_soyad")
        antrenor.ad_soyad = govde.ad_soyad
        if kullanici is not None:
            kullanici.ad_soyad = govde.ad_soyad
    if "telefon" in verilen:
        if govde.telefon is None or not govde.telefon.strip():
            raise _hata422("telefon boş olamaz")
        telefon = _telefon_normalize(govde.telefon)
        if kullanici is not None and telefon != kullanici.giris:
            if (await session.execute(select(Kullanici.id).where(Kullanici.giris == telefon))).first() is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
            await cakisma_denetle(session, telefon, kullanici.id)
            kullanici.giris = telefon
            giris_degisti = True
            await _oturumlari_iptal_et(session, kullanici.id)
        if telefon != antrenor.telefon or giris_degisti:
            degisen.append("telefon")
        antrenor.telefon = telefon
    gruplar = None
    if govde.grup_idleri is not None:
        gruplar = await _gruplari_ata(session, antrenor.id, list(dict.fromkeys(govde.grup_idleri)))
        if gruplar["eklenen"] or gruplar["cikarilan"]:
            degisen.append("grup_idleri")
    if "aktif" in verilen:
        if govde.aktif != antrenor.aktif:
            degisen.append("aktif")
        antrenor.aktif = govde.aktif
        if kullanici is not None:
            kullanici.aktif = govde.aktif
            if not govde.aktif:
                await _oturumlari_iptal_et(session, kullanici.id)
    detay: dict = {"alanlar": sorted(degisen)}
    if giris_degisti:
        detay["giris_degisti"] = True
        detay["oturumlar_kapatildi"] = True
    if gruplar is not None and (gruplar["eklenen"] or gruplar["cikarilan"]):
        detay["gruplar"] = gruplar
    await audit.kaydet(
        session, "antrenor_guncellendi", kullanici_id=yonetici.id, hedef_tur="antrenor", hedef_id=str(antrenor.id),
        ip=_ip(request), detay=detay,
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


# ---------- profil fotoğrafı ----------
# Yükleme/silme yalnız yöneticidir (antrenör kendi fotoğrafını değiştiremez).


async def _aktif_riza(session: AsyncSession, antrenor_id: uuid.UUID) -> AntrenorFotoRizasi | None:
    return (
        await session.execute(
            select(AntrenorFotoRizasi).where(
                AntrenorFotoRizasi.antrenor_id == antrenor_id, AntrenorFotoRizasi.geri_cekildi.is_(None)
            )
        )
    ).scalar_one_or_none()


@router.post("/{antrenor_id}/foto-riza", response_model=AntrenorOzet)
async def foto_riza_ver(
    antrenor_id: uuid.UUID, request: Request, yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    antrenor = await _antrenor_al(session, antrenor_id)
    if await _aktif_riza(session, antrenor.id) is None:
        session.add(AntrenorFotoRizasi(antrenor_id=antrenor.id, kaydeden_id=yonetici.id))
        await audit.kaydet(
            session, "antrenor_foto_rizasi_verildi", kullanici_id=yonetici.id, hedef_tur="antrenor",
            hedef_id=str(antrenor.id), ip=_ip(request),
        )
        try:
            await session.commit()
        except IntegrityError:  # eşzamanlı istek aynı rızayı zaten oluşturdu
            await session.rollback()
    return await _ozet(session, antrenor.id)


@router.delete("/{antrenor_id}/foto-riza", response_model=AntrenorOzet)
async def foto_riza_geri_cek(
    antrenor_id: uuid.UUID, request: Request, yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    antrenor = await _antrenor_al(session, antrenor_id)
    riza = await _aktif_riza(session, antrenor.id)
    if riza is not None:
        riza.geri_cekildi = datetime.now(timezone.utc)
        riza.geri_ceken_id = yonetici.id
        eski = antrenor.foto_anahtar
        antrenor.foto_anahtar = None
        await audit.kaydet(
            session, "antrenor_foto_rizasi_geri_cekildi", kullanici_id=yonetici.id, hedef_tur="antrenor",
            hedef_id=str(antrenor.id), ip=_ip(request), detay={"foto_silindi": eski is not None},
        )
        await session.commit()
        if eski:
            await asyncio.to_thread(depolama.sil, eski)
    return await _ozet(session, antrenor.id)


@router.post("/{antrenor_id}/foto", status_code=status.HTTP_204_NO_CONTENT)
async def foto_yukle(
    antrenor_id: uuid.UUID,
    request: Request,
    dosya: UploadFile = File(...),
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    antrenor = await _antrenor_al(session, antrenor_id)
    if await _aktif_riza(session, antrenor.id) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Fotoğraf için antrenörün rızası kaydedilmeli")
    veri = await dosya.read(FOTO_EN_COK_BAYT + 1)
    if len(veri) > FOTO_EN_COK_BAYT:
        raise HTTPException(413, "Dosya en fazla 8 MB olabilir")
    buyuk, kucuk = await asyncio.to_thread(foto_isle, veri)

    anahtar = uuid.uuid4().hex
    eski = antrenor.foto_anahtar
    await asyncio.to_thread(depolama.kaydet, anahtar, "buyuk", buyuk)
    await asyncio.to_thread(depolama.kaydet, anahtar, "kucuk", kucuk)
    antrenor.foto_anahtar = anahtar
    await audit.kaydet(
        session, "antrenor_foto_yuklendi", kullanici_id=yonetici.id, hedef_tur="antrenor", hedef_id=str(antrenor.id),
        ip=_ip(request),
    )
    try:
        await session.commit()
    except Exception:
        await asyncio.to_thread(depolama.sil, anahtar)
        raise
    if eski:
        await asyncio.to_thread(depolama.sil, eski)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{antrenor_id}/foto")
async def foto_getir(
    antrenor_id: uuid.UUID,
    request: Request,
    boyut: FotoBoyut = "kucuk",
    kullanici: Kullanici = Goruntuleyen,
    session: AsyncSession = Depends(get_session),
):
    antrenor = await session.get(Antrenor, antrenor_id)
    if antrenor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fotoğraf bulunamadı")
    veri = await asyncio.to_thread(depolama.oku, antrenor.foto_anahtar, boyut) if antrenor.foto_anahtar else None
    if veri is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fotoğraf bulunamadı")
    basliklar = {"Cache-Control": "private, no-cache", "ETag": f'"{antrenor.foto_anahtar}-{boyut}"'}
    if request.headers.get("if-none-match") == basliklar["ETag"]:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=basliklar)
    return Response(content=veri, media_type="image/jpeg", headers=basliklar)


@router.delete("/{antrenor_id}/foto", status_code=status.HTTP_204_NO_CONTENT)
async def foto_sil(
    antrenor_id: uuid.UUID, request: Request, yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    antrenor = await _antrenor_al(session, antrenor_id)
    eski = antrenor.foto_anahtar
    if eski:
        antrenor.foto_anahtar = None
        await audit.kaydet(
            session, "antrenor_foto_silindi", kullanici_id=yonetici.id, hedef_tur="antrenor",
            hedef_id=str(antrenor.id), ip=_ip(request),
        )
        await session.commit()
        await asyncio.to_thread(depolama.sil, eski)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
