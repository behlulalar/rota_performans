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


async def aktif_kullanici(
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
    return kullanici


def rol_gerekli(*roller: Rol):
    async def _kontrol(kullanici: Kullanici = Depends(aktif_kullanici)) -> Kullanici:
        if kullanici.rol not in roller:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yetkiniz yok")
        return kullanici

    return _kontrol
