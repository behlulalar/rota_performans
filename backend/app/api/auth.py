import uuid
from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.config import settings
from app.db import get_session
from app.deps import aktif_kullanici_serbest
from app.models.kullanici import Kullanici, Oturum, Rol
from app.models.ogrenci import IletisimKisisi
from app.models.program import Antrenor
from app.ratelimit import get_redis, izin_var_mi
from app.security import (
    belirtec_ozeti,
    erisim_belirteci_uret,
    normalize_giris,
    ozet_yenilenmeli_mi,
    sahte_dogrulama,
    sifre_dogru_mu,
    sifre_ozeti,
    simdi,
    yenileme_belirteci_uret,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_ADI = "rota_yenileme"
COOKIE_YOLU = "/api/auth"

IP_LIMITI = 20  # dakikada, IP başına
HESAP_DENEME_LIMITI = 5
HESAP_KILIT_DAKIKA = 15

# Hesabın var olup olmadığını sızdırmamak için tüm başarısız girişler aynı yanıtı verir.
GENEL_HATA = "Giriş bilgileri hatalı veya hesap geçici olarak kilitli."


class LoginIstegi(BaseModel):
    giris: str = Field(min_length=3, max_length=255)
    sifre: str = Field(min_length=1, max_length=256)
    beni_hatirla: bool = False


class SifreDegistirIstegi(BaseModel):
    mevcut_sifre: str = Field(min_length=1, max_length=256)
    yeni_sifre: str = Field(max_length=256)


class BelirtecYaniti(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class KullaniciYaniti(BaseModel):
    id: uuid.UUID
    rol: Rol
    giris: str
    ad_soyad: str | None = None
    sifre_degistirmeli: bool = False


def _istemci_ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _sure(hatirla: bool) -> timedelta:
    return timedelta(days=settings.hatirla_gun) if hatirla else timedelta(hours=settings.hatirlamasiz_saat)


def _cookie_yaz(response: Response, belirtec: str, hatirla: bool) -> None:
    # Hatırlamasızda max_age/expires verilmez: tarayıcı kapanınca silinen oturum çerezi olur.
    response.set_cookie(
        COOKIE_ADI,
        belirtec,
        max_age=int(_sure(True).total_seconds()) if hatirla else None,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_YOLU,
    )


def _cookie_sil(response: Response) -> None:
    response.delete_cookie(COOKIE_ADI, path=COOKIE_YOLU)


async def _oturum_ac(session: AsyncSession, kullanici: Kullanici, hatirla: bool) -> str:
    belirtec, ozet = yenileme_belirteci_uret()
    session.add(
        Oturum(
            kullanici_id=kullanici.id,
            token_ozeti=ozet,
            bitis=simdi() + _sure(hatirla),
            hatirla=hatirla,
        )
    )
    return belirtec


def _belirtec_yaniti(kullanici: Kullanici) -> BelirtecYaniti:
    return BelirtecYaniti(
        access_token=erisim_belirteci_uret(kullanici.id, kullanici.rol),
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/login", response_model=BelirtecYaniti)
async def login(
    govde: LoginIstegi,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    ip = _istemci_ip(request)
    if not await izin_var_mi(redis, f"rl:login:ip:{ip}", IP_LIMITI, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Çok fazla deneme. Lütfen biraz bekleyin.")

    giris = normalize_giris(govde.giris)
    kullanici = (await session.execute(select(Kullanici).where(Kullanici.giris == giris))).scalar_one_or_none()
    simdi_ = simdi()

    kilitli = kullanici is not None and kullanici.kilit_bitis is not None and kullanici.kilit_bitis > simdi_
    if kullanici is None or kilitli:
        sahte_dogrulama(govde.sifre)
        await audit.kaydet(
            session,
            "giris_basarisiz",
            kullanici_id=kullanici.id if kullanici else None,
            ip=ip,
            detay={"neden": "kilitli" if kilitli else "bilinmeyen_hesap"},
        )
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENEL_HATA)

    if not (sifre_dogru_mu(kullanici.sifre_ozeti, govde.sifre) and kullanici.aktif):
        kullanici.basarisiz_deneme += 1
        detay = {"neden": "hatali_sifre"}
        if kullanici.basarisiz_deneme >= HESAP_DENEME_LIMITI:
            kullanici.kilit_bitis = simdi_ + timedelta(minutes=HESAP_KILIT_DAKIKA)
            kullanici.basarisiz_deneme = 0
            detay["kilitlendi"] = True
        await audit.kaydet(session, "giris_basarisiz", kullanici_id=kullanici.id, ip=ip, detay=detay)
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENEL_HATA)

    if ozet_yenilenmeli_mi(kullanici.sifre_ozeti):
        kullanici.sifre_ozeti = sifre_ozeti(govde.sifre)
    kullanici.basarisiz_deneme = 0
    kullanici.kilit_bitis = None
    kullanici.son_giris = simdi_
    belirtec = await _oturum_ac(session, kullanici, govde.beni_hatirla)
    await audit.kaydet(session, "giris_basarili", kullanici_id=kullanici.id, ip=ip)
    await session.commit()

    _cookie_yaz(response, belirtec, govde.beni_hatirla)
    return _belirtec_yaniti(kullanici)


@router.post("/refresh", response_model=BelirtecYaniti)
async def yenile(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    yenileme: str | None = Cookie(default=None, alias=COOKIE_ADI),
):
    def reddet() -> HTTPException:
        _cookie_sil(response)
        return HTTPException(status.HTTP_401_UNAUTHORIZED, "Oturum süresi doldu, lütfen yeniden giriş yapın.")

    if not yenileme:
        raise reddet()

    oturum = (
        await session.execute(
            select(Oturum).where(Oturum.token_ozeti == belirtec_ozeti(yenileme)).with_for_update()
        )
    ).scalar_one_or_none()
    if oturum is None or oturum.bitis < simdi():
        raise reddet()

    if oturum.iptal:
        # Kullanılmış belirteç tekrar geldi: çalınmış olabilir, kullanıcının tüm oturumlarını kapat.
        await session.execute(update(Oturum).where(Oturum.kullanici_id == oturum.kullanici_id).values(iptal=True))
        await audit.kaydet(
            session, "yenileme_yeniden_kullanim", kullanici_id=oturum.kullanici_id, ip=_istemci_ip(request)
        )
        await session.commit()
        raise reddet()

    kullanici = await session.get(Kullanici, oturum.kullanici_id)
    if kullanici is None or not kullanici.aktif:
        raise reddet()

    oturum.iptal = True
    yeni = await _oturum_ac(session, kullanici, oturum.hatirla)
    await session.commit()

    _cookie_yaz(response, yeni, oturum.hatirla)
    return _belirtec_yaniti(kullanici)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def cikis(
    response: Response,
    session: AsyncSession = Depends(get_session),
    yenileme: str | None = Cookie(default=None, alias=COOKIE_ADI),
):
    if yenileme:
        await session.execute(
            update(Oturum).where(Oturum.token_ozeti == belirtec_ozeti(yenileme)).values(iptal=True)
        )
        await session.commit()
    _cookie_sil(response)


@router.get("/me", response_model=KullaniciYaniti)
async def ben(kullanici: Kullanici = Depends(aktif_kullanici_serbest), session: AsyncSession = Depends(get_session)):
    ad = kullanici.ad_soyad
    if not ad:
        ad = (
            await session.execute(select(Antrenor.ad_soyad).where(Antrenor.kullanici_id == kullanici.id).limit(1))
        ).scalar_one_or_none()
    if not ad:
        ad = (
            await session.execute(
                select(IletisimKisisi.ad_soyad)
                .where(IletisimKisisi.kullanici_id == kullanici.id)
                .order_by(IletisimKisisi.birincil.desc(), IletisimKisisi.olusturma)
                .limit(1)
            )
        ).scalar_one_or_none()
    return KullaniciYaniti(
        id=kullanici.id, rol=kullanici.rol, giris=kullanici.giris, ad_soyad=ad or None,
        sifre_degistirmeli=kullanici.sifre_degistirmeli,
    )


def _yeni_sifre_hatasi(mevcut: str, yeni: str) -> str | None:
    if len(yeni) < 10:
        return "Yeni şifre en az 10 karakter olmalı"
    if len(yeni) > 256:
        return "Yeni şifre en fazla 256 karakter olabilir"
    if not (any(c.isalpha() for c in yeni) and any(c.isdigit() for c in yeni)):
        return "Yeni şifre en az bir harf ve bir rakam içermeli"
    if yeni == mevcut:
        return "Yeni şifre mevcut şifreyle aynı olamaz"
    return None


@router.post("/sifre-degistir", status_code=status.HTTP_204_NO_CONTENT)
async def sifre_degistir(
    govde: SifreDegistirIstegi,
    request: Request,
    response: Response,
    kullanici: Kullanici = Depends(aktif_kullanici_serbest),
    session: AsyncSession = Depends(get_session),
    yenileme: str | None = Cookie(default=None, alias=COOKIE_ADI),
):
    ip = _istemci_ip(request)
    simdi_ = simdi()
    if kullanici.kilit_bitis is not None and kullanici.kilit_bitis > simdi_:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Hesap geçici olarak kilitli. Lütfen daha sonra deneyin.")

    if not sifre_dogru_mu(kullanici.sifre_ozeti, govde.mevcut_sifre):
        kullanici.basarisiz_deneme += 1
        detay = {"neden": "hatali_mevcut_sifre"}
        if kullanici.basarisiz_deneme >= HESAP_DENEME_LIMITI:
            kullanici.kilit_bitis = simdi_ + timedelta(minutes=HESAP_KILIT_DAKIKA)
            kullanici.basarisiz_deneme = 0
            detay["kilitlendi"] = True
        await audit.kaydet(session, "sifre_degistirme_basarisiz", kullanici_id=kullanici.id, ip=ip, detay=detay)
        await session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mevcut şifre hatalı")

    hata = _yeni_sifre_hatasi(govde.mevcut_sifre, govde.yeni_sifre)
    if hata:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, hata)

    kullanici.sifre_ozeti = sifre_ozeti(govde.yeni_sifre)
    kullanici.sifre_degistirmeli = False
    kullanici.basarisiz_deneme = 0
    kullanici.kilit_bitis = None
    sorgu = update(Oturum).where(Oturum.kullanici_id == kullanici.id)
    if yenileme:
        sorgu = sorgu.where(Oturum.token_ozeti != belirtec_ozeti(yenileme))
    await session.execute(sorgu.values(iptal=True))
    await audit.kaydet(session, "sifre_degistirildi", kullanici_id=kullanici.id, ip=ip)
    await session.commit()
