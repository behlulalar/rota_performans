"""Yönetici duyuruları: velilere elle yazılan mesaj (şimdilik yalnız uygulama bildirimi)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app import duyuru as dsvc
from app.db import get_session
from app.deps import rol_gerekli
from app.models.bildirim import Bildirim
from app.models.duyuru import Duyuru, DuyuruHedefTuru
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import IletisimKisisi, Ogrenci
from app.models.program import DersOturumu, Grup
from app.oturumlar import simdi
from app.schemas.duyuru import (
    DuyuruAlicisi,
    DuyuruDetay,
    DuyuruGirdi,
    DuyuruHedef,
    DuyuruIstatistik,
    DuyuruKanallari,
    DuyuruOzet,
    KanalIstatistigi,
    OnizlemeGirdi,
    OnizlemeYanit,
)

router = APIRouter(prefix="/api/duyurular", tags=["duyurular"])

Yonetici = Depends(rol_gerekli(Rol.admin))

WHATSAPP_KAPALI = "WhatsApp henüz etkin değil"


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _hedef_json(h: DuyuruHedef) -> dict:
    if h.tur == DuyuruHedefTuru.oturum:
        return {"oturum_id": str(h.oturum_id)}
    if h.tur == DuyuruHedefTuru.grup:
        return {"grup_idleri": [str(i) for i in dict.fromkeys(h.grup_idleri or [])]}
    return {}


async def _kitle(session: AsyncSession, h: DuyuruHedef) -> dsvc.Kitle:
    try:
        return await dsvc.kitleyi_coz(session, h.tur, oturum_id=h.oturum_id, grup_idleri=h.grup_idleri)
    except dsvc.HedefHatasi as e:
        raise HTTPException(422, str(e))


@router.post("/onizleme", response_model=OnizlemeYanit)
async def onizleme(govde: OnizlemeGirdi, _: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
    k = await _kitle(session, govde.hedef)
    return OnizlemeYanit(
        ogrenci=len(k.ogrenci_idleri), alici=k.alici_sayisi, push_alacak=len(k.push),
        push_yok=k.alici_sayisi - len(k.push), whatsapp_izinli=len(k.whatsapp),
    )


async def _hedef_ozetleri(session: AsyncSession, duyurular: list[Duyuru]) -> dict[uuid.UUID, str]:
    oturum_idleri = {uuid.UUID(d.hedef["oturum_id"]) for d in duyurular if d.hedef_tur == DuyuruHedefTuru.oturum and d.hedef.get("oturum_id")}
    grup_idleri = {
        uuid.UUID(g) for d in duyurular if d.hedef_tur == DuyuruHedefTuru.grup for g in d.hedef.get("grup_idleri", [])
    }
    oturumlar = {}
    if oturum_idleri:
        oturumlar = {
            o.id: f"{ad} · {o.tarih:%d.%m.%Y} {o.baslangic:%H:%M}"
            for o, ad in (
                await session.execute(
                    select(DersOturumu, Grup.ad).join(Grup, Grup.id == DersOturumu.grup_id).where(DersOturumu.id.in_(oturum_idleri))
                )
            ).all()
        }
    gruplar = {}
    if grup_idleri:
        gruplar = dict((await session.execute(select(Grup.id, Grup.ad).where(Grup.id.in_(grup_idleri)))).all())
    sonuc = {}
    for d in duyurular:
        if d.hedef_tur == DuyuruHedefTuru.tum:
            sonuc[d.id] = "Tüm aktif öğrenciler"
        elif d.hedef_tur == DuyuruHedefTuru.oturum:
            sonuc[d.id] = "Ders: " + oturumlar.get(uuid.UUID(d.hedef["oturum_id"]), "silinmiş ders")
        else:
            adlar = [gruplar.get(uuid.UUID(g), "silinmiş grup") for g in d.hedef.get("grup_idleri", [])]
            sonuc[d.id] = "Grup: " + ", ".join(adlar)
    return sonuc


async def _istatistikler(session: AsyncSession, idler: list[uuid.UUID]) -> dict[uuid.UUID, DuyuruIstatistik]:
    sonuc = {i: DuyuruIstatistik() for i in idler}
    if not idler:
        return sonuc
    satirlar = await session.execute(
        select(Bildirim.duyuru_id, Bildirim.kanal, Bildirim.durum, func.count())
        .where(Bildirim.duyuru_id.in_(idler))
        .group_by(Bildirim.duyuru_id, Bildirim.kanal, Bildirim.durum)
    )
    for did, kanal, durum, n in satirlar.all():
        k: KanalIstatistigi = getattr(sonuc[did], kanal.value)
        setattr(k, durum.value, n)
        k.toplam += n
    return sonuc


def _ozet(d: Duyuru, hedef_ozet: str, ist: DuyuruIstatistik) -> dict:
    return dict(
        id=d.id, baslik=d.baslik, metin=d.metin, olusturma=d.olusturma, hedef_tur=d.hedef_tur, hedef_ozet=hedef_ozet,
        oturum_id=d.oturum_id, kanallar=DuyuruKanallari(push=d.kanal_push, whatsapp=d.kanal_whatsapp), istatistik=ist,
    )


@router.post("", response_model=DuyuruDetay, status_code=status.HTTP_201_CREATED)
async def olustur(
    govde: DuyuruGirdi, request: Request, yonetici: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)
):
    if govde.kanallar.whatsapp:
        raise HTTPException(422, WHATSAPP_KAPALI)
    if not govde.kanallar.push:
        raise HTTPException(422, "En az bir kanal seçin")
    kitle = await _kitle(session, govde.hedef)
    if not kitle.push:
        raise HTTPException(422, "Uygulama bildirimi alacak veli yok")
    d = Duyuru(
        baslik=govde.baslik, metin=govde.metin, hedef_tur=govde.hedef.tur, hedef=_hedef_json(govde.hedef),
        kanal_push=govde.kanallar.push, kanal_whatsapp=False, olusturan_id=yonetici.id,
        oturum_id=govde.hedef.oturum_id if govde.hedef.tur == DuyuruHedefTuru.oturum else None,
    )
    session.add(d)
    await session.flush()
    eklenen = await dsvc.kuyruga_ekle(session, d, kitle, simdi())
    await audit.kaydet(
        session, "duyuru_gonderildi", kullanici_id=yonetici.id, hedef_tur="duyuru", hedef_id=str(d.id),
        ip=_ip(request), detay={"hedef_tur": d.hedef_tur.value, "ogrenci": len(kitle.ogrenci_idleri), "kuyruga": eklenen},
    )
    await session.commit()
    await session.refresh(d)
    return await _detay(session, d)


@router.get("", response_model=list[DuyuruOzet])
async def listele(
    limit: int = Query(default=50, ge=1, le=200), _: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)
):
    duyurular = list(
        (await session.execute(select(Duyuru).order_by(Duyuru.olusturma.desc(), Duyuru.id.desc()).limit(limit))).scalars()
    )
    ozetler = await _hedef_ozetleri(session, duyurular)
    ist = await _istatistikler(session, [d.id for d in duyurular])
    return [DuyuruOzet(**_ozet(d, ozetler[d.id], ist[d.id])) for d in duyurular]


async def _detay(session: AsyncSession, d: Duyuru) -> DuyuruDetay:
    ozet = (await _hedef_ozetleri(session, [d]))[d.id]
    ist = (await _istatistikler(session, [d.id]))[d.id]
    satirlar = (
        await session.execute(
            select(Bildirim, Ogrenci, IletisimKisisi)
            .join(Ogrenci, Ogrenci.id == Bildirim.ogrenci_id)
            .join(IletisimKisisi, IletisimKisisi.id == Bildirim.alici_iletisim_id)
            .where(Bildirim.duyuru_id == d.id)
            .order_by(Ogrenci.soyad, Ogrenci.ad, Bildirim.kanal, Bildirim.id)
        )
    ).all()
    alicilar = [
        DuyuruAlicisi(
            bildirim_id=b.id, ogrenci_ad=f"{o.ad} {o.soyad}", alici_ad=k.ad_soyad, kanal=b.kanal, durum=b.durum,
            hata=b.hata, gonderim_zamani=b.gonderim_zamani,
        )
        for b, o, k in satirlar
    ]
    return DuyuruDetay(**_ozet(d, ozet, ist), alicilar=alicilar)


@router.get("/{duyuru_id}", response_model=DuyuruDetay)
async def getir(duyuru_id: uuid.UUID, _: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
    d = await session.get(Duyuru, duyuru_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Duyuru bulunamadı")
    return await _detay(session, d)
