"""İki adımlı doğrulama (TOTP, RFC 6238) yardımcıları. Yalnız destek rolü için kullanılır.

Gizli anahtar veritabanında AES-GCM ile şifreli saklanır (`kimlik.gizli_sifrele`). Kurtarma kodları
yalnızca bir kez gösterilir, özetleri saklanır ve her biri tek kullanımlıktır."""
import hmac
import secrets
import time

import pyotp
from redis.asyncio import Redis

from app import kimlik
from app.security import belirtec_ozeti

ILISKILI_VERI = b"totp_gizli"
PENCERE_SANIYE = 30
TOLERANS = 1  # ±1 pencere (saat kayması)
KOD_UZUNLUK = 6
KURTARMA_ADET = 8
ISSUER = "Rota Performans"
# Karıştırılan karakterler (0/o, 1/l/i) çıkarıldı; 10 karakter ≈ 50 bit.
_KURTARMA_HARFLER = "abcdefghjkmnpqrstuvwxyz23456789"
KULLANILAN_TTL = (2 * TOLERANS + 1) * PENCERE_SANIYE


def gizli_uret() -> str:
    return pyotp.random_base32()


def sifrele(gizli: str) -> bytes:
    return kimlik.gizli_sifrele(gizli, ILISKILI_VERI)


def coz(veri: bytes) -> str:
    return kimlik.gizli_coz(veri, ILISKILI_VERI)


def uri(gizli: str, giris: str) -> str:
    return pyotp.TOTP(gizli).provisioning_uri(name=giris, issuer_name=ISSUER)


def kod_normalize(kod: str) -> str:
    return "".join(kod.split())


def kod_biciminde_mi(kod: str) -> bool:
    return len(kod) == KOD_UZUNLUK and kod.isdigit()


def eslesen_adim(gizli: str, kod: str, simdi: float | None = None) -> int | None:
    """Kod ±1 pencerede geçerliyse eşleşen zaman adımını (sayaç), değilse None döner."""
    if not kod_biciminde_mi(kod):
        return None
    t = time.time() if simdi is None else simdi
    totp = pyotp.TOTP(gizli, interval=PENCERE_SANIYE)
    bulunan = None
    for kayma in range(-TOLERANS, TOLERANS + 1):  # sabit sürede: erken çıkış yok
        adim = int(t // PENCERE_SANIYE) + kayma
        if hmac.compare_digest(totp.at(adim * PENCERE_SANIYE), kod) and bulunan is None:
            bulunan = adim
    return bulunan


async def kod_dogru_mu(redis: Redis, kullanici_id, gizli: str, kod: str) -> bool:
    """Kodu doğrular; aynı zaman adımındaki kod ikinci kez kabul edilmez (tekrar saldırısı)."""
    adim = eslesen_adim(gizli, kod)
    if adim is None:
        return False
    return bool(await redis.set(f"2fa:kullanilan:{kullanici_id}:{adim}", "1", nx=True, ex=KULLANILAN_TTL))


def kurtarma_normalize(kod: str) -> str:
    return "".join(c for c in kod.lower() if c.isalnum())


def kurtarma_ozeti(kod: str) -> str:
    return belirtec_ozeti(kurtarma_normalize(kod))


def kurtarma_kodlari_uret() -> tuple[list[str], list[str]]:
    """(kullanıcıya gösterilecek kodlar, saklanacak özetler)."""
    kodlar = []
    for _ in range(KURTARMA_ADET):
        ham = "".join(secrets.choice(_KURTARMA_HARFLER) for _ in range(10))
        kodlar.append(f"{ham[:5]}-{ham[5:]}")
    return kodlar, [kurtarma_ozeti(k) for k in kodlar]
