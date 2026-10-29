"""Yönetici bildirim ekranı: kuyruk özeti, liste, iptal ve yeniden deneme."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.bildirim import SABLONLAR, metin_olustur
from app.config import settings
from app.db import get_session
from app.deps import rol_gerekli
from app.models.bildirim import Bildirim, BildirimDurum, BildirimKanal, PushAbonelik
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import IletisimKisisi, Ogrenci
from app.oturumlar import bugun
from app.schemas.bildirim_yonetimi import (
    BildirimAlici,
    BildirimIslemi,
    BildirimListesi,
    BildirimOgrenci,
    BildirimOzeti,
    BildirimSatiri,
    DurumSayilari,
)

router = APIRouter(prefix="/api/bildirim-yonetimi", tags=["bildirim_yonetimi"])

Yonetici = Depends(rol_gerekli(Rol.admin))

SABLON_ETIKETLERI = {
    "ders_gelmedi": "Derse gelmedi",
    "ders_hakki_azaldi": "Ders hakkı azaldı",
    "ders_hakki_bitti": "Ders hakkı bitti",
    "duyuru": "Duyuru",
}


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _gun_basi(gun: date) -> datetime:
    return datetime.combine(gun, time.min, tzinfo=ZoneInfo(settings.saat_dilimi))


async def _sayilar(session: AsyncSession, baslangic: datetime, kanal: BildirimKanal | None) -> DurumSayilari:
    sorgu = select(Bildirim.durum, func.count()).where(Bildirim.olusturma >= baslangic)
    if kanal is not None:
        sorgu = sorgu.where(Bildirim.kanal == kanal)
    satirlar = await session.execute(sorgu.group_by(Bildirim.durum))
    return DurumSayilari(**{d.value: n for d, n in satirlar.all()})


@router.get("/ozet", response_model=BildirimOzeti)
async def ozet(
    kanal: BildirimKanal | None = Query(default=None),
    _: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    """`kanal` verilirse durum sayıları ve geciken bekleyenler yalnız o kanaldan sayılır."""
    t = bugun()
    son7 = await _sayilar(session, _gun_basi(t - timedelta(days=6)), kanal)
    bugunku = await _sayilar(session, _gun_basi(t), kanal)
    cihaz, kullanici = (
        await session.execute(select(func.count(), func.count(func.distinct(PushAbonelik.kullanici_id))))
    ).one()
    geciken_sorgu = select(func.count()).where(
        Bildirim.durum == BildirimDurum.bekliyor, Bildirim.planli_zaman < datetime.now(timezone.utc)
    )
    if kanal is not None:
        geciken_sorgu = geciken_sorgu.where(Bildirim.kanal == kanal)
    geciken = (await session.execute(geciken_sorgu)).scalar_one()
    return BildirimOzeti(
        son_7_gun=son7, bugun=bugunku, push_etkin=settings.push_etkin, push_cihaz_sayisi=cihaz,
        push_kullanici_sayisi=kullanici, geciken_bekleyen=geciken,
    )


@router.get("", response_model=BildirimListesi)
async def listele(
    durum: BildirimDurum | None = Query(default=None),
    kanal: BildirimKanal | None = Query(default=None),
    sablon: str | None = Query(default=None, max_length=64),
    q: str | None = Query(default=None, max_length=100),
    baslangic: date | None = Query(default=None),
    bitis: date | None = Query(default=None),
    sayfa: int = Query(default=1, ge=1),
    boyut: int = Query(default=20, ge=1, le=100),
    _: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    if sablon is not None and sablon not in SABLONLAR:
        raise HTTPException(422, "Geçersiz bildirim türü")
    if baslangic and bitis and bitis < baslangic:
        raise HTTPException(422, "Bitiş tarihi başlangıçtan önce olamaz")

    kosullar = []
    if durum is not None:
        kosullar.append(Bildirim.durum == durum)
    if kanal is not None:
        kosullar.append(Bildirim.kanal == kanal)
    if sablon is not None:
        kosullar.append(Bildirim.sablon == sablon)
    if baslangic:
        kosullar.append(Bildirim.olusturma >= _gun_basi(baslangic))
    if bitis:
        kosullar.append(Bildirim.olusturma < _gun_basi(bitis + timedelta(days=1)))
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

    toplam = (
        await session.execute(
            select(func.count()).select_from(Bildirim).join(Ogrenci, Ogrenci.id == Bildirim.ogrenci_id).where(*kosullar)
        )
    ).scalar_one()
    satirlar = (
        await session.execute(
            select(Bildirim, Ogrenci, IletisimKisisi)
            .join(Ogrenci, Ogrenci.id == Bildirim.ogrenci_id)
            .join(IletisimKisisi, IletisimKisisi.id == Bildirim.alici_iletisim_id)
            .where(*kosullar)
            .order_by(Bildirim.olusturma.desc(), Bildirim.id.desc())
            .limit(boyut)
            .offset((sayfa - 1) * boyut)
        )
    ).all()
    kayitlar = [
        BildirimSatiri(
            id=b.id, olusturma=b.olusturma, planli_zaman=b.planli_zaman, gonderim_zamani=b.gonderim_zamani,
            kanal=b.kanal, sablon=b.sablon, sablon_etiket=SABLON_ETIKETLERI.get(b.sablon, b.sablon),
            durum=b.durum, deneme=b.deneme, hata=b.hata,
            ogrenci=BildirimOgrenci(id=str(o.id), ad=o.ad, soyad=o.soyad),
            alici=BildirimAlici(ad_soyad=k.ad_soyad, rol=k.rol.value),
            metin=await metin_olustur(session, b),
        )
        for b, o, k in satirlar
    ]
    return BildirimListesi(kayitlar=kayitlar, toplam=toplam, sayfa=sayfa, boyut=boyut)


async def _kilitle(session: AsyncSession, bildirim_id: int) -> Bildirim:
    b = (
        await session.execute(select(Bildirim).where(Bildirim.id == bildirim_id).with_for_update())
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(404, "Bildirim bulunamadı")
    return b


@router.post("/{bildirim_id}/iptal", response_model=BildirimIslemi)
async def iptal(
    bildirim_id: int, request: Request, yonetici: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)
):
    b = await _kilitle(session, bildirim_id)
    if b.durum != BildirimDurum.bekliyor:
        raise HTTPException(409, "Yalnız bekleyen bildirim iptal edilebilir")
    b.durum = BildirimDurum.iptal
    await audit.kaydet(
        session, "bildirim_iptal_edildi", kullanici_id=yonetici.id, hedef_tur="bildirim", hedef_id=str(b.id),
        ip=_ip(request), detay={"kanal": b.kanal.value, "sablon": b.sablon},
    )
    await session.commit()
    return BildirimIslemi(id=b.id, durum=b.durum)


@router.post("/{bildirim_id}/yeniden-dene", response_model=BildirimIslemi)
async def yeniden_dene(
    bildirim_id: int, request: Request, yonetici: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)
):
    b = await _kilitle(session, bildirim_id)
    if b.durum != BildirimDurum.hata:
        raise HTTPException(409, "Yalnız hatalı bildirim yeniden denenebilir")
    b.durum = BildirimDurum.bekliyor
    b.planli_zaman = datetime.now(timezone.utc)
    b.deneme = 0
    await audit.kaydet(
        session, "bildirim_yeniden_denendi", kullanici_id=yonetici.id, hedef_tur="bildirim", hedef_id=str(b.id),
        ip=_ip(request), detay={"kanal": b.kanal.value, "sablon": b.sablon},
    )
    await session.commit()
    return BildirimIslemi(id=b.id, durum=b.durum)
