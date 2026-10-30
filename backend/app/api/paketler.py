import calendar
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db import get_session
from app.deps import rol_gerekli, yalniz_yonetici
from app.maskele import tutar_gizle
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import Ogrenci, OgrenciDurum
from app.models.paket import Odeme, OgrenciPaketi, OgrenciPaketiDurum, Paket
from app.schemas.paket import (
    OdemeSatiri,
    OgrenciPaketiYanit,
    PaketAta,
    PaketGuncelle,
    PaketOlustur,
    PaketYanit,
)

router = APIRouter(prefix="/api/paketler", tags=["paketler"])
ogrenci_router = APIRouter(prefix="/api/ogrenciler", tags=["paketler"])
ogrenci_paketi_router = APIRouter(prefix="/api/ogrenci-paketleri", tags=["paketler"])

Yonetici = Depends(rol_gerekli(Rol.admin))
FinansYazma = Depends(yalniz_yonetici)

IKI_HANE = Decimal("0.01")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def ay_ekle(tarih: date, ay: int) -> date:
    """Ay ekler; hedef ayda o gün yoksa ayın son gününe çeker (31 Ocak + 1 ay = 28/29 Şubat)."""
    toplam = tarih.year * 12 + (tarih.month - 1) + ay
    yil, ay_no = divmod(toplam, 12)
    ay_no += 1
    return date(yil, ay_no, min(tarih.day, calendar.monthrange(yil, ay_no)[1]))


# --- Paket tanımları ---


@router.get("", response_model=list[PaketYanit])
async def listele(
    aktif: bool | None = Query(default=None),
    kullanici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    sorgu = select(Paket).order_by(Paket.aktif.desc(), Paket.sure_ay, Paket.ad, Paket.id)
    if aktif is not None:
        sorgu = sorgu.where(Paket.aktif.is_(aktif))
    return tutar_gizle(kullanici, [PaketYanit.model_validate(p) for p in (await session.execute(sorgu)).scalars()])


@router.post("", response_model=PaketYanit, status_code=status.HTTP_201_CREATED)
async def olustur(
    govde: PaketOlustur,
    request: Request,
    yonetici: Kullanici = FinansYazma,
    session: AsyncSession = Depends(get_session),
):
    paket = Paket(
        ad=govde.ad, tur=govde.tur, ders_sayisi=govde.ders_sayisi, sure_ay=govde.sure_ay,
        varsayilan_fiyat=govde.varsayilan_fiyat, aciklama=govde.aciklama or None, aktif=True,
    )
    session.add(paket)
    await session.flush()
    await audit.kaydet(
        session, "paket_olusturuldu", kullanici_id=yonetici.id, hedef_tur="paket", hedef_id=str(paket.id),
        ip=_ip(request), detay={"ad": paket.ad, "varsayilan_fiyat": f"{paket.varsayilan_fiyat:.2f}"},
    )
    await session.commit()
    await session.refresh(paket)
    return paket


@router.patch("/{paket_id}", response_model=PaketYanit)
async def guncelle(
    paket_id: uuid.UUID,
    govde: PaketGuncelle,
    request: Request,
    yonetici: Kullanici = FinansYazma,
    session: AsyncSession = Depends(get_session),
):
    paket = (
        await session.execute(select(Paket).where(Paket.id == paket_id).with_for_update())
    ).scalar_one_or_none()
    if paket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paket bulunamadı")
    verilen = govde.model_fields_set
    for alan in ("ad", "tur", "ders_sayisi", "sure_ay", "varsayilan_fiyat", "aktif"):
        if alan in verilen and getattr(govde, alan) is None:
            raise HTTPException(422, f"{alan} boş olamaz")
        if alan in verilen:
            setattr(paket, alan, getattr(govde, alan))
    if "aciklama" in verilen:
        paket.aciklama = govde.aciklama or None  # boş metin açıklamayı siler
    await audit.kaydet(
        session, "paket_guncellendi", kullanici_id=yonetici.id, hedef_tur="paket", hedef_id=str(paket.id),
        ip=_ip(request), detay={"alanlar": sorted(verilen)},
    )
    await session.commit()
    await session.refresh(paket)
    return paket


# --- Öğrenci paketleri ---


async def _yanitlar(session: AsyncSession, kosul) -> list[OgrenciPaketiYanit]:
    odenen = (
        select(Odeme.ogrenci_paketi_id, func.coalesce(func.sum(Odeme.tutar), 0).label("toplam"))
        .where(Odeme.iptal_zamani.is_(None))
        .group_by(Odeme.ogrenci_paketi_id)
        .subquery()
    )
    satirlar = await session.execute(
        select(OgrenciPaketi, Paket.ad, func.coalesce(odenen.c.toplam, 0))
        .join(Paket, Paket.id == OgrenciPaketi.paket_id)
        .outerjoin(odenen, odenen.c.ogrenci_paketi_id == OgrenciPaketi.id)
        .where(kosul)
        .order_by(OgrenciPaketi.olusturma.desc(), OgrenciPaketi.id)
    )
    satirlar = satirlar.all()
    odemeler: dict[uuid.UUID, list[OdemeSatiri]] = {}
    if satirlar:
        kayitlar = await session.execute(
            select(Odeme, Kullanici.ad_soyad, Kullanici.giris)
            .outerjoin(Kullanici, Kullanici.id == Odeme.olusturan_id)
            .where(Odeme.ogrenci_paketi_id.in_([op.id for op, _, _ in satirlar]))
            .order_by(Odeme.tarih.desc(), Odeme.olusturma.desc(), Odeme.id)
        )
        for o, ad_soyad, giris in kayitlar.all():
            odemeler.setdefault(o.ogrenci_paketi_id, []).append(
                OdemeSatiri(
                    id=o.id, tutar=o.tutar, tarih=o.tarih, yontem=o.yontem, aciklama=o.aciklama,
                    iptal=o.iptal_zamani is not None, iptal_nedeni=o.iptal_nedeni, alan_ad=ad_soyad or giris,
                )
            )
    return [
        OgrenciPaketiYanit(
            id=op.id, ogrenci_id=op.ogrenci_id, paket_id=op.paket_id, paket_adi=ad, ders_sayisi=op.ders_sayisi,
            liste_fiyati=op.liste_fiyati, uygulanan_fiyat=op.uygulanan_fiyat, fiyat_ozel_mi=op.fiyat_ozel_mi,
            durum=op.durum, baslangic=op.baslangic, bitis=op.bitis, toplam_odenen=Decimal(toplam),
            olusturma=op.olusturma, odemeler=odemeler.get(op.id, []),
        )
        for op, ad, toplam in satirlar
    ]


@ogrenci_router.get("/{ogrenci_id}/paketler", response_model=list[OgrenciPaketiYanit])
async def ogrenci_paketleri(
    ogrenci_id: uuid.UUID, kullanici: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)
):
    ogrenci = await session.get(Ogrenci, ogrenci_id)
    if ogrenci is None or ogrenci.sentetik:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Öğrenci bulunamadı")
    return tutar_gizle(kullanici, await _yanitlar(session, OgrenciPaketi.ogrenci_id == ogrenci_id))


@ogrenci_router.post(
    "/{ogrenci_id}/paketler", response_model=OgrenciPaketiYanit, status_code=status.HTTP_201_CREATED
)
async def paket_ata(
    ogrenci_id: uuid.UUID,
    govde: PaketAta,
    request: Request,
    yonetici: Kullanici = FinansYazma,
    session: AsyncSession = Depends(get_session),
):
    # Öğrenci satırı kilitlenir: eşzamanlı iki atama "tek bekleyen paket" kuralını aşamasın.
    ogrenci = (
        await session.execute(select(Ogrenci).where(Ogrenci.id == ogrenci_id).with_for_update())
    ).scalar_one_or_none()
    if ogrenci is None or ogrenci.sentetik:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Öğrenci bulunamadı")
    if ogrenci.durum != OgrenciDurum.aktif:
        raise HTTPException(409, "Pasif öğrenciye paket atanamaz")

    nedeni = govde.ozel_fiyat_nedeni
    if govde.ozel_fiyat is None:
        if nedeni:
            raise HTTPException(422, "Özel fiyat nedeni yalnızca özel fiyat verilirse girilebilir")
    elif nedeni is None or not 3 <= len(nedeni) <= 200:
        raise HTTPException(422, "Özel fiyat için neden zorunludur (3-200 karakter)")

    paket = await session.get(Paket, govde.paket_id)
    if paket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paket bulunamadı")
    if not paket.aktif:
        raise HTTPException(409, "Pasif paket atanamaz")

    bekleyen = (
        await session.execute(
            select(OgrenciPaketi.id).where(
                OgrenciPaketi.ogrenci_id == ogrenci.id, OgrenciPaketi.durum == OgrenciPaketiDurum.odeme_bekliyor
            )
        )
    ).first()
    if bekleyen is not None:
        raise HTTPException(409, "Bu öğrencinin ödeme bekleyen bir paketi var")

    baslangic = govde.baslangic or date.today()
    liste = paket.varsayilan_fiyat
    uygulanan = govde.ozel_fiyat.quantize(IKI_HANE) if govde.ozel_fiyat is not None else liste
    ozel_mi = uygulanan != liste
    op = OgrenciPaketi(
        ogrenci_id=ogrenci.id, paket_id=paket.id, ders_sayisi=paket.ders_sayisi, liste_fiyati=liste,
        uygulanan_fiyat=uygulanan, fiyat_ozel_mi=ozel_mi, fiyat_degistiren_id=yonetici.id if ozel_mi else None,
        baslangic=baslangic, bitis=ay_ekle(baslangic, paket.sure_ay), durum=OgrenciPaketiDurum.odeme_bekliyor,
        olusturan_id=yonetici.id,
    )
    session.add(op)
    await session.flush()
    detay = {
        "ogrenci_id": str(ogrenci.id), "paket_id": str(paket.id), "liste_fiyati": f"{liste:.2f}",
        "uygulanan_fiyat": f"{uygulanan:.2f}",
    }
    if govde.ozel_fiyat is not None:
        detay["ozel_fiyat_nedeni"] = nedeni
    await audit.kaydet(
        session, "ogrenci_paketi_atandi", kullanici_id=yonetici.id, hedef_tur="ogrenci_paketi",
        hedef_id=str(op.id), ip=_ip(request), detay=detay,
    )
    await session.commit()
    return (await _yanitlar(session, OgrenciPaketi.id == op.id))[0]


@ogrenci_paketi_router.post("/{ogrenci_paketi_id}/iptal", response_model=OgrenciPaketiYanit)
async def iptal(
    ogrenci_paketi_id: uuid.UUID,
    request: Request,
    yonetici: Kullanici = FinansYazma,
    session: AsyncSession = Depends(get_session),
):
    op = (
        await session.execute(
            select(OgrenciPaketi).where(OgrenciPaketi.id == ogrenci_paketi_id).with_for_update()
        )
    ).scalar_one_or_none()
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Öğrenci paketi bulunamadı")
    if op.durum != OgrenciPaketiDurum.odeme_bekliyor:
        raise HTTPException(409, "Yalnızca ödeme bekleyen paket iptal edilebilir")
    odeme_var = (
        await session.execute(select(Odeme.id)
            .where(Odeme.ogrenci_paketi_id == op.id, Odeme.iptal_zamani.is_(None))
            .limit(1))
    ).first()
    if odeme_var is not None:
        raise HTTPException(409, "Ödemesi alınmış paket iptal edilemez")
    op.durum = OgrenciPaketiDurum.iptal
    await audit.kaydet(
        session, "ogrenci_paketi_iptal_edildi", kullanici_id=yonetici.id, hedef_tur="ogrenci_paketi",
        hedef_id=str(op.id), ip=_ip(request), detay={"ogrenci_id": str(op.ogrenci_id)},
    )
    await session.commit()
    return (await _yanitlar(session, OgrenciPaketi.id == op.id))[0]
