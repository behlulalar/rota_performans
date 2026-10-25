import calendar
import uuid
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.api.paketler import _yanitlar
from app.config import settings
from app.db import get_session
from app.deps import rol_gerekli
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import Ogrenci
from app.models.paket import Odeme, OdemeYontemi, OgrenciPaketi, OgrenciPaketiDurum, Paket
from app.models.yoklama import DersHakkiHareketi, HareketTuru, Sayac
from app.oturumlar import bugun
from app.schemas.odeme import (
    BekleyenPaket,
    OdemeAl,
    OdemeIptal,
    OdemeListe,
    OdemeListeSatiri,
    OdemeOgrenci,
    OdemeOzeti,
    YontemDagilimi,
)
from app.schemas.paket import OgrenciPaketiYanit

ogrenci_paketi_router = APIRouter(prefix="/api/ogrenci-paketleri", tags=["odemeler"])
router = APIRouter(prefix="/api/odemeler", tags=["odemeler"])

Yonetici = Depends(rol_gerekli(Rol.admin))


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


@ogrenci_paketi_router.post("/{ogrenci_paketi_id}/odeme", response_model=OgrenciPaketiYanit)
async def odeme_al(
    ogrenci_paketi_id: uuid.UUID,
    govde: OdemeAl,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    # Paket satırı kilitlenir: eşzamanlı iki ödeme tek yükleme yazabilsin.
    op = (
        await session.execute(
            select(OgrenciPaketi).where(OgrenciPaketi.id == ogrenci_paketi_id).with_for_update()
        )
    ).scalar_one_or_none()
    if op is None:
        raise HTTPException(404, "Öğrenci paketi bulunamadı")
    if op.durum == OgrenciPaketiDurum.iptal:
        raise HTTPException(409, "Bu paket iptal edilmiş, ödeme alınamaz")
    if op.durum != OgrenciPaketiDurum.odeme_bekliyor:
        raise HTTPException(409, "Bu paket için ödeme zaten alınmış")
    tarih = govde.tarih or bugun()
    if tarih > bugun():
        raise HTTPException(422, "Ödeme tarihi gelecekte olamaz")

    odeme = None
    if op.uygulanan_fiyat > 0:
        odeme = Odeme(
            ogrenci_paketi_id=op.id, tutar=op.uygulanan_fiyat, tarih=tarih, yontem=govde.yontem,
            aciklama=govde.aciklama or None, olusturan_id=yonetici.id,
        )
        session.add(odeme)
        await session.flush()
    op.durum = OgrenciPaketiDurum.odendi
    session.add(
        DersHakkiHareketi(
            ogrenci_id=op.ogrenci_id, sayac=Sayac.normal, miktar=op.ders_sayisi, tur=HareketTuru.paket_yuklemesi,
            ogrenci_paketi_id=op.id, odeme_id=odeme.id if odeme else None, olusturan_id=yonetici.id,
        )
    )
    detay = {
        "ogrenci_paketi_id": str(op.id), "tutar": f"{op.uygulanan_fiyat:.2f}", "yontem": govde.yontem.value,
        "yuklenen_ders": op.ders_sayisi,
    }
    if odeme is None:
        detay["ucretsiz_paket"] = True
    await audit.kaydet(
        session, "odeme_alindi", kullanici_id=yonetici.id, hedef_tur="ogrenci_paketi", hedef_id=str(op.id),
        ip=_ip(request), detay=detay,
    )
    await session.commit()
    return (await _yanitlar(session, OgrenciPaketi.id == op.id))[0]


@router.post("/{odeme_id}/iptal", response_model=OgrenciPaketiYanit)
async def odeme_iptal(
    odeme_id: uuid.UUID,
    govde: OdemeIptal,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    paket_id = (
        await session.execute(select(Odeme.ogrenci_paketi_id).where(Odeme.id == odeme_id))
    ).scalar_one_or_none()
    if paket_id is None:
        raise HTTPException(404, "Ödeme bulunamadı")
    # Kilit sırası her yerde aynı: önce paket, sonra ödeme.
    op = (
        await session.execute(select(OgrenciPaketi).where(OgrenciPaketi.id == paket_id).with_for_update())
    ).scalar_one()
    odeme = (
        await session.execute(select(Odeme).where(Odeme.id == odeme_id).with_for_update())
    ).scalar_one()
    if odeme.iptal_zamani is not None:
        raise HTTPException(409, "Bu ödeme zaten iptal edilmiş")

    odeme.iptal_zamani = datetime.now(ZoneInfo("UTC"))
    odeme.iptal_nedeni = govde.neden
    odeme.iptal_eden_id = yonetici.id
    yukleme = (
        await session.execute(
            select(DersHakkiHareketi).where(
                DersHakkiHareketi.odeme_id == odeme.id, DersHakkiHareketi.tur == HareketTuru.paket_yuklemesi
            )
        )
    ).scalar_one_or_none()
    if yukleme is not None:
        session.add(
            DersHakkiHareketi(
                ogrenci_id=yukleme.ogrenci_id, sayac=yukleme.sayac, miktar=-yukleme.miktar, tur=HareketTuru.iptal,
                iptal_edilen_id=yukleme.id, ogrenci_paketi_id=op.id, neden=f"Ödeme iptal edildi: {govde.neden}",
                olusturan_id=yonetici.id,
            )
        )
    op.durum = OgrenciPaketiDurum.odeme_bekliyor
    await audit.kaydet(
        session, "odeme_iptal_edildi", kullanici_id=yonetici.id, hedef_tur="odeme", hedef_id=str(odeme.id),
        ip=_ip(request),
        detay={"ogrenci_paketi_id": str(op.id), "tutar": f"{odeme.tutar:.2f}", "neden": govde.neden},
    )
    await session.commit()
    return (await _yanitlar(session, OgrenciPaketi.id == op.id))[0]


def _ay_araligi() -> tuple[date, date]:
    t = bugun()
    return t.replace(day=1), t.replace(day=calendar.monthrange(t.year, t.month)[1])


@router.get("/bekleyenler", response_model=list[BekleyenPaket])
async def bekleyenler(_: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
    satirlar = await session.execute(
        select(OgrenciPaketi, Paket.ad, Ogrenci.id, Ogrenci.ad, Ogrenci.soyad)
        .join(Paket, Paket.id == OgrenciPaketi.paket_id)
        .join(Ogrenci, Ogrenci.id == OgrenciPaketi.ogrenci_id)
        .where(OgrenciPaketi.durum == OgrenciPaketiDurum.odeme_bekliyor, Ogrenci.sentetik.is_(False))
        .order_by(OgrenciPaketi.olusturma, OgrenciPaketi.id)
    )
    bugun_ = bugun()
    sonuc = []
    for op, paket_adi, o_id, ad, soyad in satirlar.all():
        atama = op.olusturma.astimezone(ZoneInfo(settings.saat_dilimi)).date()
        sonuc.append(
            BekleyenPaket(
                ogrenci_paketi_id=op.id, ogrenci=OdemeOgrenci(id=o_id, ad=ad, soyad=soyad), paket_adi=paket_adi,
                uygulanan_fiyat=op.uygulanan_fiyat, atama_tarihi=atama, bekleme_gun=max((bugun_ - atama).days, 0),
            )
        )
    return sonuc


@router.get("", response_model=OdemeListe)
async def listele(
    baslangic: date | None = Query(default=None),
    bitis: date | None = Query(default=None),
    yontem: OdemeYontemi | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    iptal_dahil: bool = Query(default=True),
    sayfa: int = Query(default=1, ge=1),
    boyut: int = Query(default=50, ge=1, le=200),
    _: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ay_bas, ay_son = _ay_araligi()
    baslangic = baslangic or ay_bas
    bitis = bitis or ay_son
    if bitis < baslangic:
        raise HTTPException(422, "Bitiş tarihi başlangıçtan önce olamaz")

    kosullar = [Ogrenci.sentetik.is_(False), Odeme.tarih >= baslangic, Odeme.tarih <= bitis]
    if yontem is not None:
        kosullar.append(Odeme.yontem == yontem)
    if not iptal_dahil:
        kosullar.append(Odeme.iptal_zamani.is_(None))
    if q and q.strip():
        kacis = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        desen = f"%{kacis}%"
        kosullar.append(
            or_(
                Ogrenci.ad.ilike(desen, escape="\\"),
                Ogrenci.soyad.ilike(desen, escape="\\"),
                (Ogrenci.ad + " " + Ogrenci.soyad).ilike(desen, escape="\\"),
            )
        )
    govde = (
        select(Odeme)
        .join(OgrenciPaketi, OgrenciPaketi.id == Odeme.ogrenci_paketi_id)
        .join(Ogrenci, Ogrenci.id == OgrenciPaketi.ogrenci_id)
        .where(*kosullar)
    )
    toplam = (await session.execute(select(func.count()).select_from(govde.subquery()))).scalar_one()

    aktif = Odeme.iptal_zamani.is_(None)
    dagilim_sorgu = (
        select(Odeme.yontem, func.sum(Odeme.tutar), func.count())
        .select_from(Odeme)
        .join(OgrenciPaketi, OgrenciPaketi.id == Odeme.ogrenci_paketi_id)
        .join(Ogrenci, Ogrenci.id == OgrenciPaketi.ogrenci_id)
        .where(*kosullar, aktif)
        .group_by(Odeme.yontem)
        .order_by(Odeme.yontem)
    )
    dagilim = [
        YontemDagilimi(yontem=y, tutar=Decimal(t), adet=a) for y, t, a in (await session.execute(dagilim_sorgu)).all()
    ]
    ozet = OdemeOzeti(
        toplam_tutar=sum((d.tutar for d in dagilim), Decimal("0")), adet=sum(d.adet for d in dagilim),
        yontem_dagilimi=dagilim,
    )

    satirlar = await session.execute(
        select(Odeme, Paket.ad, Ogrenci.id, Ogrenci.ad, Ogrenci.soyad, Kullanici.ad_soyad, Kullanici.giris)
        .join(OgrenciPaketi, OgrenciPaketi.id == Odeme.ogrenci_paketi_id)
        .join(Paket, Paket.id == OgrenciPaketi.paket_id)
        .join(Ogrenci, Ogrenci.id == OgrenciPaketi.ogrenci_id)
        .outerjoin(Kullanici, Kullanici.id == Odeme.olusturan_id)
        .where(*kosullar)
        .order_by(Odeme.tarih.desc(), Odeme.olusturma.desc(), Odeme.id)
        .limit(boyut)
        .offset((sayfa - 1) * boyut)
    )
    kayitlar = [
        OdemeListeSatiri(
            id=o.id, ogrenci_paketi_id=o.ogrenci_paketi_id, tarih=o.tarih,
            ogrenci=OdemeOgrenci(id=o_id, ad=ad, soyad=soyad), paket_adi=paket_adi, tutar=o.tutar,
            yontem=o.yontem, aciklama=o.aciklama, iptal=o.iptal_zamani is not None, iptal_nedeni=o.iptal_nedeni,
            alan_ad=k_ad or k_giris,
        )
        for o, paket_adi, o_id, ad, soyad, k_ad, k_giris in satirlar.all()
    ]
    return OdemeListe(kayitlar=kayitlar, toplam=toplam, sayfa=sayfa, boyut=boyut, ozet=ozet)
