"""T.C. kimlik / pasaport numarası: doğrulama, şifreleme ve tekrar kontrolü için özet.

Veritabanına numara düz metin yazılmaz. `sifrele` okunabilir ama yalnızca anahtarla çözülebilen
değeri, `ozet` ise geri çevrilemeyen (HMAC) değeri üretir. Özet, aynı kişinin ikinci kez kaydedilmesini
yakalamak içindir.
"""
import base64
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

_ILISKILI_VERI = b"kimlik_no"
_NONCE_UZUNLUK = 12


class KimlikHatasi(ValueError):
    pass


def normalize(numara: str) -> str:
    return "".join(numara.split()).upper()


def tc_gecerli_mi(numara: str) -> bool:
    """11 haneli T.C. kimlik numarası algoritması."""
    n = normalize(numara)
    if len(n) != 11 or not n.isdigit() or n[0] == "0":
        return False
    d = [int(x) for x in n]
    d10 = ((sum(d[0:9:2]) * 7) - sum(d[1:8:2])) % 10
    d11 = sum(d[:10]) % 10
    return d[9] == d10 and d[10] == d11


def _anahtar(b64: str) -> bytes:
    anahtar = base64.urlsafe_b64decode(b64.encode())
    if len(anahtar) != 32:
        raise KimlikHatasi("Anahtar 32 bayt olmalı")
    return anahtar


def sifrele(numara: str) -> bytes:
    nonce = os.urandom(_NONCE_UZUNLUK)
    sifreli = AESGCM(_anahtar(settings.kimlik_sifreleme_anahtari)).encrypt(
        nonce, normalize(numara).encode(), _ILISKILI_VERI
    )
    return nonce + sifreli


def coz(veri: bytes) -> str:
    nonce, sifreli = veri[:_NONCE_UZUNLUK], veri[_NONCE_UZUNLUK:]
    try:
        return AESGCM(_anahtar(settings.kimlik_sifreleme_anahtari)).decrypt(nonce, sifreli, _ILISKILI_VERI).decode()
    except InvalidTag as hata:
        raise KimlikHatasi("Şifreli veri çözülemedi (anahtar yanlış veya veri bozuk)") from hata


def ozet(numara: str) -> str:
    return hmac.new(
        _anahtar(settings.kimlik_ozet_anahtari), normalize(numara).encode(), hashlib.sha256
    ).hexdigest()


def maskele(numara: str) -> str:
    """Listelerde gösterim: ilk 3 ve son 2 hane görünür."""
    n = normalize(numara)
    return n if len(n) < 6 else f"{n[:3]}{'*' * (len(n) - 5)}{n[-2:]}"


# Genel amaçlı gizli metin şifreleme (aynı anahtar, ayrı ilişkili veri): TOTP gizli anahtarı gibi.
def gizli_sifrele(metin: str, iliskili: bytes) -> bytes:
    nonce = os.urandom(_NONCE_UZUNLUK)
    return nonce + AESGCM(_anahtar(settings.kimlik_sifreleme_anahtari)).encrypt(nonce, metin.encode(), iliskili)


def gizli_coz(veri: bytes, iliskili: bytes) -> str:
    nonce, sifreli = veri[:_NONCE_UZUNLUK], veri[_NONCE_UZUNLUK:]
    try:
        return AESGCM(_anahtar(settings.kimlik_sifreleme_anahtari)).decrypt(nonce, sifreli, iliskili).decode()
    except InvalidTag as hata:
        raise KimlikHatasi("Şifreli veri çözülemedi (anahtar yanlış veya veri bozuk)") from hata
