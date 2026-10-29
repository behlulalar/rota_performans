"""Kulüp ayarları (yalnız yönetici): kulüp bilgileri ve bildirim süreleri. Tek satır, yoksa varsayılanlar."""
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app import telefon as telefon_modulu
from app.bildirim import AZALDI_ESIGI, GERI_ALMA_SURESI
from app.db import get_session
from app.deps import rol_gerekli
from app.models.ayarlar import KulupAyari
from app.models.kullanici import Kullanici, Rol
from app.schemas.ayarlar import AyarGuncelle, AyarYaniti

router = APIRouter(prefix="/api/ayarlar", tags=["ayarlar"])

Yonetici = Depends(rol_gerekli(Rol.admin))

VARSAYILAN_AD = "Rota Performans Akademi"
EPOSTA_DESENI = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _hata422(mesaj: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, mesaj)


def _yanit(a: KulupAyari | None) -> AyarYaniti:
    if a is None:
        return AyarYaniti(
            ad=VARSAYILAN_AD, telefon=None, eposta=None, adres=None,
            geri_alma_dakika=int(GERI_ALMA_SURESI.total_seconds() // 60), azaldi_esigi=AZALDI_ESIGI,
        )
    return AyarYaniti.model_validate(a, from_attributes=True)


@router.get("", response_model=AyarYaniti)
async def getir(_: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
    return _yanit(await session.get(KulupAyari, 1))


@router.put("", response_model=AyarYaniti)
async def guncelle(
    govde: AyarGuncelle,
    request: Request,
    kullanici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    gelen = govde.model_dump(exclude_unset=True)
    if "ad" in gelen:
        ad = (gelen["ad"] or "").strip()
        if len(ad) < 2:
            raise _hata422("Kulüp adı en az 2 karakter olmalı")
        gelen["ad"] = ad
    for alan in ("geri_alma_dakika", "azaldi_esigi"):
        if alan in gelen and gelen[alan] is None:
            raise _hata422("Bu alan boş bırakılamaz")
    if "telefon" in gelen:
        t = (gelen["telefon"] or "").strip()
        try:
            gelen["telefon"] = telefon_modulu.normalize(t) if t else None
        except ValueError as hata:
            raise _hata422(str(hata))
    if "eposta" in gelen:
        e = (gelen["eposta"] or "").strip()
        if e and not EPOSTA_DESENI.match(e):
            raise _hata422("Geçerli bir e-posta adresi girin")
        gelen["eposta"] = e or None
    if "adres" in gelen:
        gelen["adres"] = (gelen["adres"] or "").strip() or None

    satir = await session.get(KulupAyari, 1)
    if satir is None:
        # Varsayılanlar açıkça yazılır (flush öncesi nitelikler boş kalmasın).
        satir = KulupAyari(id=1, ad=VARSAYILAN_AD, geri_alma_dakika=int(GERI_ALMA_SURESI.total_seconds() // 60),
                           azaldi_esigi=AZALDI_ESIGI)
        session.add(satir)
    onceki = _yanit(satir).model_dump()
    degisen = []
    for alan, deger in gelen.items():
        if onceki[alan] != deger:
            degisen.append(alan)
        setattr(satir, alan, deger)
    if degisen:
        await audit.kaydet(
            session, "ayar_guncellendi", kullanici_id=kullanici.id, hedef_tur="kulup_ayari", hedef_id="1",
            ip=request.client.host if request.client else "bilinmiyor", detay={"alanlar": degisen},
        )
    await session.commit()
    await session.refresh(satir)
    return _yanit(satir)
