import uuid
from datetime import date, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db import get_session
from app.deps import rol_gerekli
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import Ogrenci, OgrenciDurum
from app.models.program import Antrenor, DersOturumu, Grup, GrupProgrami, OgrenciGrup, OturumDurum, TelafiPlani
from app.models.yoklama import Yoklama
from app.oturumlar import URETIM_GUN, bugun, oturumlari_uret
from app.schemas.grup import (
    GrupAntrenor,
    GrupDetay,
    GrupGuncelle,
    GrupOgrenci,
    GrupOlustur,
    GrupOzet,
    OgrenciEkle,
    ProgramSlot,
)

router = APIRouter(prefix="/api/gruplar", tags=["gruplar"])

BULUNAMADI = "Grup bulunamadı"

Yonetici = Depends(rol_gerekli(Rol.admin))


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _hata422(mesaj: str) -> HTTPException:
    return HTTPException(422, mesaj)


def _yas(dogum: date) -> int:
    bugun = date.today()
    return bugun.year - dogum.year - ((bugun.month, bugun.day) < (dogum.month, dogum.day))


def _saat(deger: str) -> time:
    return time.fromisoformat(deger)


def _programi_dogrula(program: list[ProgramSlot]) -> None:
    gorulen = set()
    for s in program:
        anahtar = (s.gun, s.baslangic)
        if anahtar in gorulen:
            raise _hata422("Aynı gün ve başlangıç saatinde birden fazla ders olamaz")
        gorulen.add(anahtar)
    ids = [s.id for s in program if s.id is not None]
    if len(ids) != len(set(ids)):
        raise _hata422("Program satırı kimliği tekrar ediyor")


async def _antrenor_dogrula(session: AsyncSession, antrenor_id: uuid.UUID) -> None:
    antrenor = await session.get(Antrenor, antrenor_id)
    if antrenor is None or not antrenor.aktif:
        raise _hata422("Antrenör bulunamadı veya pasif")


async def _grup_al(session: AsyncSession, grup_id: uuid.UUID, kilitle: bool = False) -> Grup:
    sorgu = select(Grup).where(Grup.id == grup_id)
    if kilitle:
        sorgu = sorgu.with_for_update()
    grup = (await session.execute(sorgu)).scalar_one_or_none()
    if grup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, BULUNAMADI)
    return grup


async def _ogrenci_sayisi(session: AsyncSession, grup_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(OgrenciGrup).where(OgrenciGrup.grup_id == grup_id, OgrenciGrup.bitis.is_(None))
        )
    ).scalar_one()


async def _ozetler(session: AsyncSession, kosullar: list) -> list[GrupOzet]:
    gruplar = list((await session.execute(select(Grup).where(*kosullar).order_by(Grup.ad, Grup.id))).scalars())
    if not gruplar:
        return []
    idler = [g.id for g in gruplar]
    sayilar = dict(
        (
            await session.execute(
                select(OgrenciGrup.grup_id, func.count())
                .where(OgrenciGrup.grup_id.in_(idler), OgrenciGrup.bitis.is_(None))
                .group_by(OgrenciGrup.grup_id)
            )
        ).all()
    )
    programlar: dict[uuid.UUID, list[ProgramSlot]] = {}
    slotlar = await session.execute(
        select(GrupProgrami).where(GrupProgrami.grup_id.in_(idler)).order_by(GrupProgrami.gun, GrupProgrami.baslangic)
    )
    for s in slotlar.scalars():
        programlar.setdefault(s.grup_id, []).append(
            ProgramSlot(id=s.id, gun=s.gun, baslangic=s.baslangic.strftime("%H:%M"), bitis=s.bitis.strftime("%H:%M"))
        )
    antrenor_idleri = {g.antrenor_id for g in gruplar if g.antrenor_id}
    antrenorler = {}
    if antrenor_idleri:
        antrenorler = {
            a.id: a
            for a in (await session.execute(select(Antrenor).where(Antrenor.id.in_(antrenor_idleri)))).scalars()
        }
    return [
        GrupOzet(
            id=g.id,
            ad=g.ad,
            antrenor=GrupAntrenor(id=g.antrenor_id, ad_soyad=antrenorler[g.antrenor_id].ad_soyad)
            if g.antrenor_id in antrenorler
            else None,
            kontenjan=g.kontenjan,
            aktif=g.aktif,
            ogrenci_sayisi=sayilar.get(g.id, 0),
            program=programlar.get(g.id, []),
        )
        for g in gruplar
    ]


async def _detay(session: AsyncSession, grup_id: uuid.UUID) -> GrupDetay:
    ozet = (await _ozetler(session, [Grup.id == grup_id]))[0]
    satirlar = await session.execute(
        select(Ogrenci, OgrenciGrup.baslangic)
        .join(OgrenciGrup, OgrenciGrup.ogrenci_id == Ogrenci.id)
        .where(OgrenciGrup.grup_id == grup_id, OgrenciGrup.bitis.is_(None))
        .order_by(Ogrenci.soyad, Ogrenci.ad, Ogrenci.id)
    )
    ogrenciler = [
        GrupOgrenci(
            id=o.id, ad=o.ad, soyad=o.soyad, yas=_yas(o.dogum_tarihi), foto_var=o.foto_anahtar is not None,
            katilim_baslangic=baslangic,
        )
        for o, baslangic in satirlar.all()
    ]
    return GrupDetay(**ozet.model_dump(), ogrenciler=ogrenciler)


@router.get("", response_model=list[GrupOzet])
async def listele(
    aktif: bool | None = Query(default=None),
    _: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    return await _ozetler(session, [] if aktif is None else [Grup.aktif.is_(aktif)])


@router.post("", response_model=GrupDetay, status_code=status.HTTP_201_CREATED)
async def olustur(
    govde: GrupOlustur,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    _programi_dogrula(govde.program)
    if govde.antrenor_id is not None:
        await _antrenor_dogrula(session, govde.antrenor_id)
    grup = Grup(ad=govde.ad, antrenor_id=govde.antrenor_id, kontenjan=govde.kontenjan, aktif=True)
    session.add(grup)
    await session.flush()
    for s in govde.program:
        session.add(GrupProgrami(grup_id=grup.id, gun=s.gun, baslangic=_saat(s.baslangic), bitis=_saat(s.bitis)))
    await audit.kaydet(
        session, "grup_olusturuldu", kullanici_id=yonetici.id, hedef_tur="grup", hedef_id=str(grup.id), ip=_ip(request)
    )
    await session.commit()
    return await _detay(session, grup.id)


@router.get("/{grup_id}", response_model=GrupDetay)
async def getir(grup_id: uuid.UUID, _: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
    await _grup_al(session, grup_id)
    return await _detay(session, grup_id)


@router.patch("/{grup_id}", response_model=GrupDetay)
async def guncelle(
    grup_id: uuid.UUID,
    govde: GrupGuncelle,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    # Kilit, eşzamanlı üye eklemeyle kontenjan karşılaştırmasının yarışmaması için.
    grup = await _grup_al(session, grup_id, kilitle=True)
    verilen = govde.model_fields_set
    for alan in ("ad", "kontenjan", "aktif"):
        if alan in verilen and getattr(govde, alan) is None:
            raise _hata422(f"{alan} boş olamaz")
    if "antrenor_id" in verilen and govde.antrenor_id is not None:
        await _antrenor_dogrula(session, govde.antrenor_id)
    if "kontenjan" in verilen and govde.kontenjan < await _ogrenci_sayisi(session, grup.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Kontenjan mevcut öğrenci sayısından az olamaz")
    for alan in ("ad", "antrenor_id", "kontenjan", "aktif"):
        if alan in verilen:
            setattr(grup, alan, getattr(govde, alan))
    await audit.kaydet(
        session, "grup_guncellendi", kullanici_id=yonetici.id, hedef_tur="grup", hedef_id=str(grup.id),
        ip=_ip(request), detay={"alanlar": sorted(verilen)},
    )
    await session.commit()
    return await _detay(session, grup.id)


@router.put("/{grup_id}/program", response_model=GrupDetay)
async def program_degistir(
    grup_id: uuid.UUID,
    program: list[ProgramSlot],
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    grup = await _grup_al(session, grup_id, kilitle=True)
    _programi_dogrula(program)
    mevcut = {
        s.id: s for s in (await session.execute(select(GrupProgrami).where(GrupProgrami.grup_id == grup.id))).scalars()
    }
    if any(s.id is not None and s.id not in mevcut for s in program):
        raise _hata422("Program satırı bu gruba ait değil")
    korunan = {s.id for s in program if s.id is not None}
    # Saati, günü değişen ya da silinen satırların önceden üretilmiş ileri tarihli dersleri yeniden üretilmek üzere kaldırılır.
    degisen = {
        sid
        for sid, satir in mevcut.items()
        if sid not in korunan
        or any(
            s.id == sid and (s.gun, _saat(s.baslangic), _saat(s.bitis)) != (satir.gun, satir.baslangic, satir.bitis)
            for s in program
        )
    }
    if degisen:
        await session.execute(
            delete(DersOturumu).where(
                DersOturumu.grup_programi_id.in_(degisen),
                DersOturumu.tarih >= bugun(),
                DersOturumu.durum == OturumDurum.planli,
                ~exists().where(Yoklama.oturum_id == DersOturumu.id),
                ~exists().where(TelafiPlani.oturum_id == DersOturumu.id),
            )
        )
    for sid, satir in mevcut.items():
        if sid not in korunan:
            await session.delete(satir)
    await session.flush()
    # İki mevcut satırın (gün, başlangıç) değerini birbiriyle takas etmek tekil kısıta takılıp 422 döner.
    for s in program:
        if s.id is not None:
            satir = mevcut[s.id]
            satir.gun, satir.baslangic, satir.bitis = s.gun, _saat(s.baslangic), _saat(s.bitis)
        else:
            session.add(GrupProgrami(grup_id=grup.id, gun=s.gun, baslangic=_saat(s.baslangic), bitis=_saat(s.bitis)))
    await audit.kaydet(
        session, "grup_programi_degisti", kullanici_id=yonetici.id, hedef_tur="grup", hedef_id=str(grup.id),
        ip=_ip(request),
    )
    try:
        await session.flush()
        if grup.aktif:
            await oturumlari_uret(session, bugun(), bugun() + timedelta(days=URETIM_GUN), [grup.id])
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise _hata422("Aynı gün ve başlangıç saatinde birden fazla ders olamaz")
    return await _detay(session, grup.id)


@router.post("/{grup_id}/ogrenciler", response_model=GrupDetay)
async def ogrenci_ekle(
    grup_id: uuid.UUID,
    govde: OgrenciEkle,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    grup = await _grup_al(session, grup_id, kilitle=True)
    ogrenci = await session.get(Ogrenci, govde.ogrenci_id)
    if ogrenci is None or ogrenci.sentetik:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Öğrenci bulunamadı")
    if ogrenci.durum != OgrenciDurum.aktif:
        raise _hata422("Pasif öğrenci gruba eklenemez")
    if not grup.aktif:
        raise _hata422("Pasif gruba öğrenci eklenemez")
    var = (
        await session.execute(
            select(OgrenciGrup.id).where(
                OgrenciGrup.grup_id == grup.id, OgrenciGrup.ogrenci_id == ogrenci.id, OgrenciGrup.bitis.is_(None)
            )
        )
    ).first()
    if var is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Öğrenci zaten bu grupta")
    if await _ogrenci_sayisi(session, grup.id) >= grup.kontenjan:
        raise HTTPException(status.HTTP_409_CONFLICT, "Grup kontenjanı dolu")
    session.add(OgrenciGrup(ogrenci_id=ogrenci.id, grup_id=grup.id))
    await audit.kaydet(
        session, "grup_ogrenci_eklendi", kullanici_id=yonetici.id, hedef_tur="grup", hedef_id=str(grup.id),
        ip=_ip(request), detay={"ogrenci_id": str(ogrenci.id)},
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Öğrenci zaten bu grupta")
    return await _detay(session, grup.id)


@router.delete("/{grup_id}/ogrenciler/{ogrenci_id}", response_model=GrupDetay)
async def ogrenci_cikar(
    grup_id: uuid.UUID,
    ogrenci_id: uuid.UUID,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    grup = await _grup_al(session, grup_id, kilitle=True)
    uyelik = (
        await session.execute(
            select(OgrenciGrup).where(
                OgrenciGrup.grup_id == grup.id, OgrenciGrup.ogrenci_id == ogrenci_id, OgrenciGrup.bitis.is_(None)
            )
        )
    ).scalar_one_or_none()
    if uyelik is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Öğrenci bu grupta değil")
    uyelik.bitis = func.current_date()
    await audit.kaydet(
        session, "grup_ogrenci_cikarildi", kullanici_id=yonetici.id, hedef_tur="grup", hedef_id=str(grup.id),
        ip=_ip(request), detay={"ogrenci_id": str(ogrenci_id)},
    )
    await session.commit()
    return await _detay(session, grup.id)
