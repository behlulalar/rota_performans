import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.config import settings
from app import telefon
from app.models.kullanici import Rol

_hasher = PasswordHasher()
# Bilinmeyen kullanıcıda da aynı işlem süresini harcamak için sahte özet.
_SAHTE_OZET = _hasher.hash("sahte-sifre-zamanlama-icin")

JWT_ALGORITMA = "HS256"


def simdi() -> datetime:
    return datetime.now(timezone.utc)


def normalize_giris(giris: str) -> str:
    giris = giris.strip().lower()
    # Telefonla girişte boşluk, tire ve parantez önemsizdir; e-postaya dokunulmaz.
    if "@" in giris:
        return giris
    return telefon.giris_icin(giris) or telefon.sade(giris)


def sifre_ozeti(sifre: str) -> str:
    return _hasher.hash(sifre)


def sifre_dogru_mu(ozet: str, sifre: str) -> bool:
    try:
        return _hasher.verify(ozet, sifre)
    except (VerifyMismatchError, InvalidHashError):
        return False


def sahte_dogrulama(sifre: str) -> None:
    sifre_dogru_mu(_SAHTE_OZET, sifre)


def ozet_yenilenmeli_mi(ozet: str) -> bool:
    return _hasher.check_needs_rehash(ozet)


def erisim_belirteci_uret(kullanici_id: uuid.UUID, rol: Rol) -> str:
    simdi_ = simdi()
    yuk = {
        "sub": str(kullanici_id),
        "rol": rol.value,
        "typ": "access",
        "iat": simdi_,
        "exp": simdi_ + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(yuk, settings.jwt_secret, algorithm=JWT_ALGORITMA)


def erisim_belirteci_coz(belirtec: str) -> dict:
    yuk = jwt.decode(belirtec, settings.jwt_secret, algorithms=[JWT_ALGORITMA])
    if yuk.get("typ") != "access":
        raise jwt.InvalidTokenError("yanlış belirteç türü")
    return yuk


def yenileme_belirteci_uret() -> tuple[str, str]:
    belirtec = secrets.token_urlsafe(48)
    return belirtec, belirtec_ozeti(belirtec)


def belirtec_ozeti(belirtec: str) -> str:
    return hashlib.sha256(belirtec.encode()).hexdigest()
