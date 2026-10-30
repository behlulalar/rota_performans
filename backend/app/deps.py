import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.kullanici import Kullanici, Rol
from app.security import erisim_belirteci_coz

_bearer = HTTPBearer(auto_error=False)


def _yetkisiz() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Kimlik doğrulaması gerekli",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def aktif_kullanici_serbest(
    kimlik: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Kullanici:
    if kimlik is None:
        raise _yetkisiz()
    try:
        yuk = erisim_belirteci_coz(kimlik.credentials)
        kullanici_id = uuid.UUID(yuk["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _yetkisiz()
    # Rol her istekte veritabanından okunur, belirteçteki rol yetki için kullanılmaz.
    kullanici = await session.get(Kullanici, kullanici_id)
    if kullanici is None or not kullanici.aktif:
        raise _yetkisiz()
    if kullanici.rol == Rol.destek and not kullanici.totp_aktif:
        # Destek hesabı 2FA kurulmadan oturum alamaz; 2FA CLI ile sıfırlanmışsa eski belirteçler de kapanır.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="İki adımlı doğrulama gerekli", headers={"X-Hata-Kodu": "ikili_dogrulama"}
        )
    return kullanici


async def aktif_kullanici(kullanici: Kullanici = Depends(aktif_kullanici_serbest)) -> Kullanici:
    """Geçici şifreyle girilmişse şifre değiştirilene kadar korumalı uç noktalar kapalıdır."""
    if kullanici.sifre_degistirmeli:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Şifrenizi değiştirmeniz gerekiyor",
            headers={"X-Hata-Kodu": "sifre_degistirmeli"},
        )
    return kullanici


def rol_gerekli(*roller: Rol):
    # Yönetici yetkisi isteyen her uç teknik destek hesabını da kabul eder (destek ⊇ yönetici).
    # Yalnız destek'e özel uçlar rol_gerekli(Rol.destek) ile yönetici eklenmeden kapatılır.
    if Rol.admin in roller:
        roller = (*roller, Rol.destek)

    async def _kontrol(kullanici: Kullanici = Depends(aktif_kullanici)) -> Kullanici:
        if kullanici.rol not in roller:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yetkiniz yok")
        return kullanici

    return _kontrol


async def yalniz_yonetici(kullanici: Kullanici = Depends(rol_gerekli(Rol.admin))) -> Kullanici:
    """Finansal yazma işlemleri (ödeme, paket satışı/tanımı): teknik destek tutarları göremez ve işlem yapamaz."""
    if kullanici.rol == Rol.destek:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Teknik destek hesabı finansal işlem yapamaz")
    return kullanici
