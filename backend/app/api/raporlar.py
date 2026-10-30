import calendar
import csv
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.config import settings
from app.db import get_session
from app.deps import rol_gerekli, yalniz_yonetici
from app.maskele import tutar_gizle
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import Ogrenci
from app.models.paket import Odeme, OdemeYontemi, OgrenciPaketi, OgrenciPaketiDurum, Paket
from app.oturumlar import bugun
from app.schemas.rapor import (
    GelirAy,
    GelirBekleyen,
    GelirGun,
    GelirOzeti,
    GelirPaket,
    GelirRaporu,
    GelirYontem,
    RaporDonem,
)

router = APIRouter(prefix="/api/raporlar", tags=["raporlar"])

Yonetici = Depends(rol_gerekli(Rol.admin))

SIFIR = Decimal("0")
GECIKME_GUN = 7
SERI_AY = 12
EN_FAZLA_GUN = 366
YONTEM_ETIKETI = {
    OdemeYontemi.nakit: "Nakit",
    OdemeYontemi.havale_eft: "Havale/EFT",
    OdemeYontemi.diger: "Diğer",
}


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _ay_basi(yil: int, ay: int) -> date:
    return date(yil, ay, 1)


def _ay_sonu(yil: int, ay: int) -> date:
    return date(yil, ay, calendar.monthrange(yil, ay)[1])


def _ay_kaydir(yil: int, ay: int, fark: int) -> tuple[int, int]:
    i = yil * 12 + (ay - 1) + fark
    return i // 12, i % 12 + 1


def _gun_baslangici(gun: date) -> datetime:
    """Kulüp saat diliminde günün başlangıcı (zaman damgalı sütunlarla karşılaştırmak için)."""
    return datetime.combine(gun, time.min, tzinfo=ZoneInfo(settings.saat_dilimi))


def _odeme_tabani(*sutunlar):
    """Gerçek (sentetik olmayan) öğrencilerin ödemeleri; kişisel veri çekilmez."""
    return (
        select(*sutunlar)
        .select_from(Odeme)
        .join(OgrenciPaketi, OgrenciPaketi.id == Odeme.ogrenci_paketi_id)
        .join(Ogrenci, Ogrenci.id == OgrenciPaketi.ogrenci_id)
        .where(Ogrenci.sentetik.is_(False))
    )


def _yuzde(parca: Decimal, butun: Decimal) -> float:
    return round(float(parca * 100 / butun), 2) if butun else 0.0


@router.get("/gelir", response_model=GelirRaporu)
async def gelir_raporu(
    yil: int | None = Query(default=None, ge=2000, le=2100),
    ay: int | None = Query(default=None, ge=1, le=12),
    kullanici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    t = bugun()
    yil = yil if yil is not None else t.year
    ay = ay if ay is not None else t.month
    bas, son = _ay_basi(yil, ay), _ay_sonu(yil, ay)
    onceki_yil, onceki_ay = _ay_kaydir(yil, ay, -1)
    onceki_bas, onceki_son = _ay_basi(onceki_yil, onceki_ay), _ay_sonu(onceki_yil, onceki_ay)
    aktif = Odeme.iptal_zamani.is_(None)
    donemde = (Odeme.tarih >= bas) & (Odeme.tarih <= son)
    onceki_donemde = (Odeme.tarih >= onceki_bas) & (Odeme.tarih <= onceki_son)

    def toplam(kosul):
        return func.coalesce(func.sum(Odeme.tutar).filter(kosul), 0)

    # Özet: tek sorguda dönem + önceki ay.
    (tahsilat, adet, iptal_tutar, iptal_adet, onceki) = (
        await session.execute(
            _odeme_tabani(
                toplam(donemde & aktif),
                func.count().filter(donemde & aktif),
                toplam(donemde & ~aktif),
                func.count().filter(donemde & ~aktif),
                toplam(onceki_donemde & aktif),
            ).where(Odeme.tarih >= onceki_bas, Odeme.tarih <= son)
        )
    ).one()
    tahsilat, iptal_tutar, onceki = Decimal(tahsilat), Decimal(iptal_tutar), Decimal(onceki)

    # İndirim: dönemde (geçerli) ödeme alınan paketlerin liste − uygulanan farkı, yalnız özel fiyatlılar.
    odenen_paketler = (
        _odeme_tabani(OgrenciPaketi.id).where(donemde, aktif).distinct().scalar_subquery()
    )
    indirim = (
        await session.execute(
            select(func.coalesce(func.sum(OgrenciPaketi.liste_fiyati - OgrenciPaketi.uygulanan_fiyat), 0)).where(
                OgrenciPaketi.id.in_(odenen_paketler), OgrenciPaketi.fiyat_ozel_mi.is_(True)
            )
        )
    ).scalar_one()

    # Ücretsiz paket: ödeme satırı olmayan "ödendi" paketler; atama tarihi (kulüp saatiyle) dönemde olanlar.
    ucretsiz = (
        await session.execute(
            select(func.count())
            .select_from(OgrenciPaketi)
            .join(Ogrenci, Ogrenci.id == OgrenciPaketi.ogrenci_id)
            .where(
                Ogrenci.sentetik.is_(False),
                OgrenciPaketi.durum == OgrenciPaketiDurum.odendi,
                ~select(Odeme.id).where(Odeme.ogrenci_paketi_id == OgrenciPaketi.id).exists(),
                OgrenciPaketi.olusturma >= _gun_baslangici(bas),
                OgrenciPaketi.olusturma < _gun_baslangici(son + timedelta(days=1)),
            )
        )
    ).scalar_one()

    # Bekleyenler: dönemden bağımsız, şu anki durum. Gecikmiş: bekleme_gun > 7 (bekleyenler ucuyla aynı kural).
    gecikmis_sinir = _gun_baslangici(t - timedelta(days=GECIKME_GUN))
    gecikmis = OgrenciPaketi.olusturma < gecikmis_sinir
    b_adet, b_tutar, g_adet, g_tutar = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(OgrenciPaketi.uygulanan_fiyat), 0),
                func.count().filter(gecikmis),
                func.coalesce(func.sum(OgrenciPaketi.uygulanan_fiyat).filter(gecikmis), 0),
            )
            .select_from(OgrenciPaketi)
            .join(Ogrenci, Ogrenci.id == OgrenciPaketi.ogrenci_id)
            .where(OgrenciPaketi.durum == OgrenciPaketiDurum.odeme_bekliyor, Ogrenci.sentetik.is_(False))
        )
    ).one()

    yontem_satirlari = (
        await session.execute(
            _odeme_tabani(Odeme.yontem, func.sum(Odeme.tutar), func.count())
            .where(donemde, aktif)
            .group_by(Odeme.yontem)
            .order_by(Odeme.yontem)
        )
    ).all()
    paket_satirlari = (
        await session.execute(
            _odeme_tabani(Paket.ad, func.sum(Odeme.tutar), func.count())
            .join(Paket, Paket.id == OgrenciPaketi.paket_id)
            .where(donemde, aktif)
            .group_by(Paket.id, Paket.ad)
            .order_by(func.sum(Odeme.tutar).desc(), Paket.ad)
        )
    ).all()
    gun_satirlari = (
        await session.execute(
            _odeme_tabani(Odeme.tarih, func.sum(Odeme.tutar), func.count())
            .where(donemde, aktif)
            .group_by(Odeme.tarih)
        )
    ).all()
    gunluk_harita = {g: (Decimal(tu), a) for g, tu, a in gun_satirlari}
    gunluk = []
    for i in range((son - bas).days + 1):
        g = bas + timedelta(days=i)
        tu, a = gunluk_harita.get(g, (SIFIR, 0))
        gunluk.append(GelirGun(tarih=g, tutar=tu, adet=a))

    # Aylık seri: tek GROUP BY, boş aylar sıfırla doldurulur.
    seri_yil, seri_ay = _ay_kaydir(yil, ay, -(SERI_AY - 1))
    y_sut, a_sut = extract("year", Odeme.tarih), extract("month", Odeme.tarih)
    ay_satirlari = (
        await session.execute(
            _odeme_tabani(y_sut, a_sut, func.sum(Odeme.tutar), func.count())
            .where(Odeme.tarih >= _ay_basi(seri_yil, seri_ay), Odeme.tarih <= son, aktif)
            .group_by(y_sut, a_sut)
        )
    ).all()
    ay_harita = {(int(y), int(a)): (Decimal(tu), n) for y, a, tu, n in ay_satirlari}
    aylik = []
    for i in range(SERI_AY):
        y, a = _ay_kaydir(seri_yil, seri_ay, i)
        tu, n = ay_harita.get((y, a), (SIFIR, 0))
        aylik.append(GelirAy(yil=y, ay=a, tutar=tu, adet=n))

    yanit = GelirRaporu(
        donem=RaporDonem(yil=yil, ay=ay, baslangic=bas, bitis=son),
        ozet=GelirOzeti(
            toplam_tahsilat=tahsilat,
            odeme_adedi=adet,
            ortalama_odeme=(tahsilat / adet).quantize(Decimal("0.01")) if adet else SIFIR,
            onceki_ay_tahsilat=onceki,
            degisim_yuzde=round(float((tahsilat - onceki) * 100 / onceki), 2) if onceki else None,
            iptal_edilen_tutar=iptal_tutar,
            iptal_adedi=iptal_adet,
            indirim_toplami=Decimal(indirim),
            ucretsiz_paket_adedi=ucretsiz,
        ),
        bekleyen=GelirBekleyen(
            adet=b_adet, tutar=Decimal(b_tutar), gecikmis_adet=g_adet, gecikmis_tutar=Decimal(g_tutar)
        ),
        yontem_dagilimi=[
            GelirYontem(yontem=y, tutar=Decimal(tu), adet=n, yuzde=_yuzde(Decimal(tu), tahsilat))
            for y, tu, n in yontem_satirlari
        ],
        paket_dagilimi=[GelirPaket(paket_adi=ad, tutar=Decimal(tu), adet=n) for ad, tu, n in paket_satirlari],
        gunluk=gunluk,
        aylik_seri=aylik,
    )
    return tutar_gizle(kullanici, yanit)


def _csv_guvenli(deger: str | None) -> str:
    """CSV enjeksiyonu: formül olarak yorumlanabilecek hücrelerin başına tek tırnak eklenir."""
    d = deger or ""
    return "'" + d if d[:1] in ("=", "+", "-", "@", "\t", "\r") else d


@router.get("/gelir.csv")
async def gelir_csv(
    request: Request,
    baslangic: date | None = Query(default=None),
    bitis: date | None = Query(default=None),
    yonetici: Kullanici = Depends(yalniz_yonetici),
    session: AsyncSession = Depends(get_session),
):
    t = bugun()
    baslangic = baslangic or t.replace(day=1)
    bitis = bitis or _ay_sonu(t.year, t.month)
    if bitis < baslangic:
        raise HTTPException(422, "Bitiş tarihi başlangıçtan önce olamaz")
    if (bitis - baslangic).days + 1 > EN_FAZLA_GUN:
        raise HTTPException(422, f"Tarih aralığı en fazla {EN_FAZLA_GUN} gün olabilir")

    satirlar = (
        await session.execute(
            _odeme_tabani(
                Odeme, Ogrenci.ad, Ogrenci.soyad, Paket.ad, Kullanici.ad_soyad, Kullanici.giris
            )
            .join(Paket, Paket.id == OgrenciPaketi.paket_id)
            .outerjoin(Kullanici, Kullanici.id == Odeme.olusturan_id)
            .where(Odeme.tarih >= baslangic, Odeme.tarih <= bitis)
            .order_by(Odeme.tarih, Odeme.olusturma, Odeme.id)
        )
    ).all()

    cikti = io.StringIO()
    yazar = csv.writer(cikti, delimiter=";", lineterminator="\r\n")
    yazar.writerow(["Tarih", "Öğrenci", "Paket", "Tutar", "Yöntem", "Durum", "Açıklama", "İşlemi yapan"])
    for o, ad, soyad, paket_adi, k_ad, k_giris in satirlar:
        yazar.writerow(
            [
                o.tarih.isoformat(),
                _csv_guvenli(f"{ad} {soyad}"),
                _csv_guvenli(paket_adi),
                f"{o.tutar:.2f}".replace(".", ","),
                YONTEM_ETIKETI[o.yontem],
                "İptal" if o.iptal_zamani is not None else "Geçerli",
                _csv_guvenli(o.aciklama),
                _csv_guvenli(k_ad or k_giris),
            ]
        )
    await audit.kaydet(
        session, "rapor_disa_aktarildi", kullanici_id=yonetici.id, hedef_tur="gelir_raporu", ip=_ip(request),
        detay={"baslangic": baslangic.isoformat(), "bitis": bitis.isoformat(), "satir_sayisi": len(satirlar)},
    )
    await session.commit()
    ad = f"gelir-{baslangic:%Y%m%d}-{bitis:%Y%m%d}.csv"
    return Response(
        content="﻿" + cikti.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{ad}"'},
    )
