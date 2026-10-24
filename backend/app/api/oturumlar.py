import uuid
from datetime import date
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, exists, func, or_, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import audit, ders_hakki
from app.config import settings
from app.db import get_session
from app.deps import rol_gerekli
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import Ogrenci
from app.models.program import Antrenor, DersOturumu, Grup, OgrenciGrup, OturumDurum, TelafiPlani
from app.models.yoklama import Yoklama
from app.oturumlar import bugun, oturumlari_uret, simdi, yoklama_acilis_zamani
from app.schemas.oturum import (
    EN_COK_GUN,
    OturumAntrenor,
    OturumDetay,
    OturumGrup,
    OturumOgrenci,
    OturumOzet,
    UretGirdi,
    UretYanit,
    YoklamaGirdi,
)

router = APIRouter(prefix="/api", tags=["oturumlar"])

BULUNAMADI = "Ders oturumu bulunamadı"

Yonetici = Depends(rol_gerekli(Rol.admin))
Yetkili = Depends(rol_gerekli(Rol.admin, Rol.antrenor))


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _etkin_antrenor():
    """Oturumun antrenörü: yerine bakan varsa o, yoksa grubun antrenörü."""
    return func.coalesce(DersOturumu.antrenor_id, Grup.antrenor_id)


async def _kendi_antrenor_kaydi(session: AsyncSession, kullanici: Kullanici) -> Antrenor:
    antrenor = (
        await session.execute(select(Antrenor).where(Antrenor.kullanici_id == kullanici.id))
    ).scalar_one_or_none()
    if antrenor is None or not antrenor.aktif:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yetkiniz yok")
    return antrenor


async def _ozetler(session: AsyncSession, kosullar: list) -> list[OturumOzet]:
    ant = aliased(Antrenor)
    yoklama_var = exists().where(Yoklama.oturum_id == DersOturumu.id)
    satirlar = (
        await session.execute(
            select(DersOturumu, Grup.ad, ant.id, ant.ad_soyad, yoklama_var)
            .join(Grup, Grup.id == DersOturumu.grup_id)
            .outerjoin(ant, ant.id == _etkin_antrenor())
            .where(*kosullar)
            .order_by(DersOturumu.tarih, DersOturumu.baslangic, Grup.ad, DersOturumu.id)
        )
    ).all()
    if not satirlar:
        return []
    idler = [o.id for o, *_ in satirlar]
    # O tarihteki aktif üyelikler ile telafi planı tek sorguda sayılır (aynı öğrenci bir kez).
    uyeler = (
        select(DersOturumu.id.label("oturum_id"), OgrenciGrup.ogrenci_id.label("ogrenci_id"))
        .join(OgrenciGrup, OgrenciGrup.grup_id == DersOturumu.grup_id)
        .where(
            DersOturumu.id.in_(idler),
            OgrenciGrup.baslangic <= DersOturumu.tarih,
            or_(OgrenciGrup.bitis.is_(None), OgrenciGrup.bitis >= DersOturumu.tarih),
        )
    )
    telafi = select(TelafiPlani.oturum_id, TelafiPlani.ogrenci_id).where(TelafiPlani.oturum_id.in_(idler))
    birlesik = union_all(uyeler, telafi).subquery()
    sayilar = dict(
        (
            await session.execute(
                select(birlesik.c.oturum_id, func.count(func.distinct(birlesik.c.ogrenci_id))).group_by(
                    birlesik.c.oturum_id
                )
            )
        ).all()
    )
    return [
        OturumOzet(
            id=o.id,
            tarih=o.tarih,
            baslangic=o.baslangic,
            bitis=o.bitis,
            durum=o.durum,
            grup=OturumGrup(id=o.grup_id, ad=grup_ad),
            antrenor=OturumAntrenor(id=ant_id, ad_soyad=ant_ad) if ant_id is not None else None,
            ogrenci_sayisi=sayilar.get(o.id, 0),
            yoklama_alindi=bool(var),
        )
        for o, grup_ad, ant_id, ant_ad, var in satirlar
    ]


async def _oturum_al(session: AsyncSession, oturum_id: uuid.UUID, kullanici: Kullanici) -> OturumOzet:
    """Oturumu getirir. Antrenör yalnızca kendi oturumunu görebilir."""
    ozetler = await _ozetler(session, [DersOturumu.id == oturum_id])
    if not ozetler:
        raise HTTPException(status.HTTP_404_NOT_FOUND, BULUNAMADI)
    ozet = ozetler[0]
    if kullanici.rol == Rol.antrenor:
        antrenor = await _kendi_antrenor_kaydi(session, kullanici)
        if ozet.antrenor is None or ozet.antrenor.id != antrenor.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yetkiniz yok")
    return ozet


async def _ogrenci_listesi(session: AsyncSession, ozet: OturumOzet) -> list[tuple[Ogrenci, bool]]:
    """Oturumun öğrencileri: o tarihteki aktif üyeler ve telafi planındakiler (telafi_mi = True)."""
    uyeler = (
        await session.execute(
            select(Ogrenci)
            .join(OgrenciGrup, OgrenciGrup.ogrenci_id == Ogrenci.id)
            .where(
                OgrenciGrup.grup_id == ozet.grup.id,
                OgrenciGrup.baslangic <= ozet.tarih,
                or_(OgrenciGrup.bitis.is_(None), OgrenciGrup.bitis >= ozet.tarih),
            )
        )
    ).scalars()
    telafiler = (
        await session.execute(
            select(Ogrenci)
            .join(TelafiPlani, TelafiPlani.ogrenci_id == Ogrenci.id)
            .where(TelafiPlani.oturum_id == ozet.id)
        )
    ).scalars()
    kayit: dict[uuid.UUID, tuple[Ogrenci, bool]] = {o.id: (o, False) for o in uyeler}
    for o in telafiler:
        kayit[o.id] = (o, True)
    return sorted(kayit.values(), key=lambda t: (t[0].soyad, t[0].ad, str(t[0].id)))


async def _detay(session: AsyncSession, ozet: OturumOzet) -> OturumDetay:
    liste = await _ogrenci_listesi(session, ozet)
    idler = [o.id for o, _ in liste]
    yoklamalar = {}
    if idler:
        yoklamalar = dict(
            (
                await session.execute(
                    select(Yoklama.ogrenci_id, Yoklama.durum).where(
                        Yoklama.oturum_id == ozet.id, Yoklama.ogrenci_id.in_(idler)
                    )
                )
            ).all()
        )
    bakiyeler = await ders_hakki.bakiyeler(session, idler)
    return OturumDetay(
        **ozet.model_dump(),
        ogrenciler=[
            OturumOgrenci(
                ogrenci_id=o.id,
                ad=o.ad,
                soyad=o.soyad,
                foto_var=o.foto_anahtar is not None,
                telafi_mi=telafi_mi,
                yoklama=yoklamalar.get(o.id),
                bakiye=bakiyeler[o.id],
            )
            for o, telafi_mi in liste
        ],
    )


def _aralik_dogrula(baslangic: date, bitis: date) -> None:
    if bitis < baslangic:
        raise HTTPException(422, "Bitiş tarihi başlangıçtan önce olamaz")
    if (bitis - baslangic).days + 1 > EN_COK_GUN:
        raise HTTPException(422, f"Aralık en çok {EN_COK_GUN} gün olabilir")


@router.post("/oturumlar/uret", response_model=UretYanit)
async def uret(
    govde: UretGirdi,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    sayi = await oturumlari_uret(session, govde.baslangic, govde.bitis)
    await audit.kaydet(
        session, "oturumlar_uretildi", kullanici_id=yonetici.id, hedef_tur="ders_oturumu", ip=_ip(request),
        detay={"olusturulan": sayi},
    )
    await session.commit()
    return UretYanit(olusturulan=sayi)


@router.get("/takvim", response_model=list[OturumOzet])
async def takvim(
    baslangic: date,
    bitis: date,
    antrenor_id: uuid.UUID | None = Query(default=None),
    kullanici: Kullanici = Yetkili,
    session: AsyncSession = Depends(get_session),
):
    _aralik_dogrula(baslangic, bitis)
    kosullar = [DersOturumu.tarih >= baslangic, DersOturumu.tarih <= bitis]
    if kullanici.rol == Rol.antrenor:
        # Antrenör yalnızca kendi oturumlarını görür, antrenor_id parametresi yok sayılır.
        antrenor_id = (await _kendi_antrenor_kaydi(session, kullanici)).id
    if antrenor_id is not None:
        kosullar.append(
            or_(DersOturumu.antrenor_id == antrenor_id, and_(DersOturumu.antrenor_id.is_(None), Grup.antrenor_id == antrenor_id))
        )
    return await _ozetler(session, kosullar)


@router.get("/oturumlar/{oturum_id}", response_model=OturumDetay)
async def getir(oturum_id: uuid.UUID, kullanici: Kullanici = Yetkili, session: AsyncSession = Depends(get_session)):
    ozet = await _oturum_al(session, oturum_id, kullanici)
    return await _detay(session, ozet)


@router.put("/oturumlar/{oturum_id}/yoklama", response_model=OturumDetay)
async def yoklama_al(
    oturum_id: uuid.UUID,
    govde: list[YoklamaGirdi],
    request: Request,
    kullanici: Kullanici = Yetkili,
    session: AsyncSession = Depends(get_session),
):
    ozet = await _oturum_al(session, oturum_id, kullanici)
    if ozet.tarih > bugun():
        raise HTTPException(422, "Gelecek tarihli derse yoklama alınamaz")
    # Antrenör yoklamayı ders başlamadan en erken 15 dakika önce alabilir (yanlış derse girişi önler).
    # Yönetici bu kurala tabi değildir, her zaman düzeltebilir. Saat sunucudan, kulübün saat diliminde.
    if kullanici.rol == Rol.antrenor:
        acilis = yoklama_acilis_zamani(ozet.tarih, ozet.baslangic)
        if simdi() < acilis:
            yerel = acilis.astimezone(ZoneInfo(settings.saat_dilimi))
            raise HTTPException(422, f"Yoklama {yerel:%H:%M}'te açılır (ders başlamadan 15 dakika önce)")
    if ozet.durum == OturumDurum.iptal:
        raise HTTPException(422, "İptal edilmiş derse yoklama alınamaz")
    idler = [g.ogrenci_id for g in govde]
    if len(idler) != len(set(idler)):
        raise HTTPException(422, "Aynı öğrenci birden fazla kez gönderilmiş")
    liste = {o.id: telafi_mi for o, telafi_mi in await _ogrenci_listesi(session, ozet)}
    if any(i not in liste for i in idler):
        raise HTTPException(422, "Öğrenci bu dersin listesinde değil")
    an = simdi()
    # Satırlar kilitlenir: aynı anda çalışan işçi ya da ikinci istek aynı yoklamayı değiştirmesin.
    mevcut = {}
    if idler:
        mevcut = {
            y.ogrenci_id: y
            for y in (
                await session.execute(
                    select(Yoklama)
                    .where(Yoklama.oturum_id == oturum_id, Yoklama.ogrenci_id.in_(idler))
                    .with_for_update()
                )
            ).scalars()
        }
    for g in govde:
        y = mevcut.get(g.ogrenci_id)
        if y is None:
            await ders_hakki.yoklama_olustur(
                session,
                oturum_id=oturum_id,
                ogrenci_id=g.ogrenci_id,
                durum=g.durum,
                telafi_mi=liste[g.ogrenci_id],
                isaretleyen_id=kullanici.id,
                simdi=an,
            )
        else:
            await ders_hakki.yoklama_uygula(session, y, g.durum, kullanici.id, an)
    await audit.kaydet(
        session, "yoklama_alindi", kullanici_id=kullanici.id, hedef_tur="ders_oturumu", hedef_id=str(oturum_id),
        ip=_ip(request),
        detay={
            "toplam": len(govde),
            "geldi": sum(1 for g in govde if g.durum.value == "geldi"),
            "gelmedi": sum(1 for g in govde if g.durum.value == "gelmedi"),
        },
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Yoklama aynı anda başka biri tarafından değiştirildi, tekrar deneyin")
    ozet = (await _ozetler(session, [DersOturumu.id == oturum_id]))[0]
    return await _detay(session, ozet)
