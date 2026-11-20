"""Antrenör paneli: bugünün dersleri, kendi öğrencilerinin devamı ve kendi profili. Yalnız antrenör rolü; yöneticinin kendi ekranları vardır."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.api.oturumlar import _antrenor_kosulu, _kendi_antrenor_kaydi, _ozetler
from app.config import settings
from app.devam import grup_devamlari
from app.db import get_session
from app.deps import rol_gerekli
from app.models.kullanici import Kullanici, Rol
from app.models.program import DersOturumu, Grup, OturumDurum, TelafiPlani
from app.models.yoklama import Yoklama
from app.oturumlar import bugun, simdi, yoklama_acilis_zamani
from app.schemas.antrenor_paneli import (
    AntrenorProfil,
    AntrenorProfilGuncelle,
    BugunDers,
    BugunOzet,
    BugunYanit,
)
from app.schemas.devam import GrupDevami
from app.schemas.oturum import OturumOzet

router = APIRouter(prefix="/api/antrenor", tags=["antrenor-paneli"])

Antrenor_ = Depends(rol_gerekli(Rol.antrenor))

GECMIS_GUN = 7


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


async def _dersler(session: AsyncSession, ozetler: list[OturumOzet], an) -> list[BugunDers]:
    if not ozetler:
        return []
    idler = [o.id for o in ozetler]
    alinan = dict(
        (
            await session.execute(
                select(Yoklama.oturum_id, func.count()).where(Yoklama.oturum_id.in_(idler)).group_by(Yoklama.oturum_id)
            )
        ).all()
    )
    telafi = dict(
        (
            await session.execute(
                select(TelafiPlani.oturum_id, func.count())
                .where(TelafiPlani.oturum_id.in_(idler))
                .group_by(TelafiPlani.oturum_id)
            )
        ).all()
    )
    sonuc = []
    for o in ozetler:
        n = alinan.get(o.id, 0)
        if o.durum == OturumDurum.iptal:
            durum = "iptal"
        elif n == 0 and o.ogrenci_sayisi > 0:
            durum = "bekliyor"
        elif n < o.ogrenci_sayisi:
            durum = "eksik"
        else:
            durum = "alindi"
        sonuc.append(
            BugunDers(
                id=o.id, tarih=o.tarih, grup=o.grup, baslangic=o.baslangic, bitis=o.bitis, durum=o.durum,
                beklenen_ogrenci=o.ogrenci_sayisi, yoklama_alinan=n, yoklama_durumu=durum,
                yoklama_acik=an >= yoklama_acilis_zamani(o.tarih, o.baslangic),
                telafi_sayisi=telafi.get(o.id, 0),
            )
        )
    return sonuc


def _bitti_mi(d: BugunDers, an) -> bool:
    yerel = an.astimezone(ZoneInfo(settings.saat_dilimi))
    return (d.tarih, d.bitis) <= (yerel.date(), yerel.time())


@router.get("/bugun", response_model=BugunYanit)
async def bugun_dersleri(kullanici: Kullanici = Antrenor_, session: AsyncSession = Depends(get_session)):
    antrenor = await _kendi_antrenor_kaydi(session, kullanici)
    an = simdi()
    gun = bugun(an)
    ozetler = await _ozetler(
        session,
        [DersOturumu.tarih >= gun - timedelta(days=GECMIS_GUN - 1), DersOturumu.tarih <= gun, _antrenor_kosulu(antrenor.id)],
    )
    tum = await _dersler(session, ozetler, an)
    bugunku = [d for d in tum if d.tarih == gun]
    # Planlı, yoklaması tamamlanmamış ve henüz bitmemiş ilk ders (sürmekte olan dahil).
    siradaki = next(
        (d.id for d in bugunku if d.durum == OturumDurum.planli and d.yoklama_durumu != "alindi" and not _bitti_mi(d, an)),
        None,
    )
    eksikler = [d for d in tum if d.yoklama_durumu in ("bekliyor", "eksik") and _bitti_mi(d, an)]
    return BugunYanit(
        tarih=gun,
        dersler=bugunku,
        siradaki=siradaki,
        ozet=BugunOzet(
            ders_sayisi=sum(1 for d in bugunku if d.durum != OturumDurum.iptal),
            toplam_ogrenci=sum(d.beklenen_ogrenci for d in bugunku if d.durum != OturumDurum.iptal),
            yoklama_bekleyen=sum(1 for d in eksikler if d.tarih == gun),
        ),
        eksik_yoklamalar=eksikler,
    )


# ---------- profil ----------


async def _profil(session: AsyncSession, kullanici: Kullanici) -> AntrenorProfil:
    antrenor = await _kendi_antrenor_kaydi(session, kullanici)
    return AntrenorProfil(id=antrenor.id, foto_var=antrenor.foto_anahtar is not None, ad_soyad=antrenor.ad_soyad, telefon=antrenor.telefon, giris=kullanici.giris)


@router.get("/ogrencilerim", response_model=list[GrupDevami])
async def ogrencilerim(kullanici: Kullanici = Antrenor_, session: AsyncSession = Depends(get_session)):
    """Antrenörün sorumlu olduğu aktif grupların öğrencileri ve devam özetleri."""
    antrenor = await _kendi_antrenor_kaydi(session, kullanici)
    gruplar = (
        await session.execute(select(Grup).where(Grup.antrenor_id == antrenor.id, Grup.aktif.is_(True)).order_by(Grup.ad))
    ).scalars().all()
    return await grup_devamlari(session, list(gruplar), bugun())


@router.get("/profil", response_model=AntrenorProfil)
async def profil(kullanici: Kullanici = Antrenor_, session: AsyncSession = Depends(get_session)):
    return await _profil(session, kullanici)


@router.patch("/profil", response_model=AntrenorProfil)
async def profil_guncelle(
    govde: AntrenorProfilGuncelle,
    request: Request,
    kullanici: Kullanici = Antrenor_,
    session: AsyncSession = Depends(get_session),
):
    antrenor = await _kendi_antrenor_kaydi(session, kullanici)
    verilen = govde.model_fields_set
    if "ad_soyad" in verilen:
        if govde.ad_soyad is None:
            raise HTTPException(422, "ad_soyad boş olamaz")
        antrenor.ad_soyad = govde.ad_soyad
        kullanici.ad_soyad = govde.ad_soyad
    # Giriş bilgisi (telefon) buradan değişmez: yalnız yönetici değiştirir; hesap ele geçirilirse kilit dışı kalınmasın.
    await audit.kaydet(
        session, "antrenor_profil_guncellendi", kullanici_id=kullanici.id, hedef_tur="antrenor",
        hedef_id=str(antrenor.id), ip=_ip(request), detay={"alanlar": sorted(verilen)},
    )
    await session.commit()
    return await _profil(session, kullanici)
