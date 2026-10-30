"""Yönetim komutları.

Örnek:
    docker compose run --rm backend python -m app.cli admin-olustur ornek@kulup.com
"""
import argparse
import asyncio
import getpass
import os
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select, update

from app.config import settings
from app.db import SessionLocal, engine
from app import audit, telefon
from app.models.kullanici import Kullanici, Oturum, Rol
from app.security import normalize_giris, sifre_ozeti

MIN_SIFRE_UZUNLUK = 12
# E2E test destek hesabı (yalnız e2e-tohum; üretimde kullanılmaz). Ortamdan geçersiz kılınabilir.
E2E_DESTEK_GIRIS = "destek@rota.test"
E2E_DESTEK_SIFRE = "Destek-test-sifre-123"


async def admin_olustur(giris: str) -> int:
    giris = normalize_giris(giris)
    if _giris_dogrula(giris) is None:
        return 1
    sifre = getpass.getpass("Şifre: ")
    if len(sifre) < MIN_SIFRE_UZUNLUK:
        print(f"Şifre en az {MIN_SIFRE_UZUNLUK} karakter olmalı.", file=sys.stderr)
        return 1
    if sifre != getpass.getpass("Şifre (tekrar): "):
        print("Şifreler eşleşmiyor.", file=sys.stderr)
        return 1

    async with SessionLocal() as session:
        var = (await session.execute(select(Kullanici).where(Kullanici.giris == giris))).scalar_one_or_none()
        if var is not None:
            print("Bu giriş zaten kayıtlı.", file=sys.stderr)
            return 1
        session.add(Kullanici(rol=Rol.admin, giris=giris, sifre_ozeti=sifre_ozeti(sifre)))
        await session.commit()
    print("Yönetici oluşturuldu.")
    return 0


def _giris_dogrula(giris: str) -> str | None:
    """E-posta/telefon biçimini denetler; hata varsa mesajı yazdırıp None döner."""
    if "@" in giris:
        try:
            validate_email(giris, check_deliverability=False)
        except EmailNotValidError as hata:
            print(f"Geçersiz e-posta adresi: {hata}", file=sys.stderr)
            return None
    elif telefon.giris_icin(giris) is None:
        print("Giriş bir e-posta adresi veya +90 ardından 10 haneli telefon numarası olmalı.", file=sys.stderr)
        return None
    return giris


async def destek_olustur(giris: str) -> int:
    """Teknik destek hesabı oluşturur (şifre burada belirlenir; 2FA ilk girişte kurulur)."""
    giris = normalize_giris(giris)
    if _giris_dogrula(giris) is None:
        return 1
    sifre = getpass.getpass("Şifre: ")
    if len(sifre) < MIN_SIFRE_UZUNLUK:
        print(f"Şifre en az {MIN_SIFRE_UZUNLUK} karakter olmalı.", file=sys.stderr)
        return 1
    if sifre != getpass.getpass("Şifre (tekrar): "):
        print("Şifreler eşleşmiyor.", file=sys.stderr)
        return 1

    async with SessionLocal() as session:
        var = (await session.execute(select(Kullanici).where(Kullanici.giris == giris))).scalar_one_or_none()
        if var is not None:
            print("Bu giriş zaten kayıtlı.", file=sys.stderr)
            return 1
        session.add(Kullanici(rol=Rol.destek, giris=giris, sifre_ozeti=sifre_ozeti(sifre), ad_soyad="Teknik Destek"))
        await session.commit()
    print("Teknik destek hesabı oluşturuldu. İlk girişte (destek paneli) iki adımlı doğrulama kurulacak.")
    return 0


async def destek_2fa_sifirla(giris: str) -> int:
    """Destek hesabının 2FA'sını siler: anahtar, kurtarma kodları ve tüm oturumlar. Sonraki girişte yeniden kurulur."""
    giris = normalize_giris(giris)
    async with SessionLocal() as session:
        k = (await session.execute(select(Kullanici).where(Kullanici.giris == giris))).scalar_one_or_none()
        if k is None or k.rol != Rol.destek:
            print("Bu girişe ait bir destek hesabı yok.", file=sys.stderr)
            return 1
        k.totp_sifreli = None
        k.totp_aktif = False
        k.totp_kurtarma = None
        k.basarisiz_deneme = 0
        k.kilit_bitis = None
        await session.execute(update(Oturum).where(Oturum.kullanici_id == k.id).values(iptal=True))
        await audit.kaydet(session, "destek_2fa_sifirlandi_cli", kullanici_id=k.id, hedef_tur="kullanici", hedef_id=str(k.id))
        await session.commit()
    print("İki adımlı doğrulama sıfırlandı; sonraki girişte yeniden kurulacak.")
    return 0


async def e2e_tohum() -> int:
    """E2E testleri için yönetici hesabını oluşturur (varsa şifresini günceller).

    Üretimde ve geliştirmede ÇALIŞMAZ: yalnızca ENV=test veya ENV=e2e iken.
    """
    if settings.env not in ("test", "e2e"):
        print(f"e2e-tohum yalnızca ENV=test veya ENV=e2e iken çalışır (şu an ENV={settings.env}).", file=sys.stderr)
        return 1
    giris = normalize_giris(os.environ.get("E2E_ADMIN_GIRIS", ""))
    sifre = os.environ.get("E2E_ADMIN_SIFRE", "")
    if not giris or not sifre:
        print("E2E_ADMIN_GIRIS ve E2E_ADMIN_SIFRE ortam değişkenleri zorunlu.", file=sys.stderr)
        return 1
    if len(sifre) < MIN_SIFRE_UZUNLUK:
        print(f"Şifre en az {MIN_SIFRE_UZUNLUK} karakter olmalı.", file=sys.stderr)
        return 1

    destek_giris = normalize_giris(os.environ.get("E2E_DESTEK_GIRIS", E2E_DESTEK_GIRIS))
    destek_sifre = os.environ.get("E2E_DESTEK_SIFRE", E2E_DESTEK_SIFRE)

    async with SessionLocal() as session:
        # Test destek hesabı: sabit şifre, 2FA KURULMAMIŞ (testler kurulum akışını kendisi yürütür).
        d = (await session.execute(select(Kullanici).where(Kullanici.giris == destek_giris))).scalar_one_or_none()
        if d is None:
            session.add(
                Kullanici(rol=Rol.destek, giris=destek_giris, sifre_ozeti=sifre_ozeti(destek_sifre), ad_soyad="Test Destek")
            )
        elif d.rol == Rol.destek:
            d.sifre_ozeti = sifre_ozeti(destek_sifre)
            d.aktif = True
            d.basarisiz_deneme = 0
            d.kilit_bitis = None
            d.sifre_degistirmeli = False
            d.totp_sifreli = None
            d.totp_aktif = False
            d.totp_kurtarma = None
            await session.execute(update(Oturum).where(Oturum.kullanici_id == d.id).values(iptal=True))
        var = (await session.execute(select(Kullanici).where(Kullanici.giris == giris))).scalar_one_or_none()
        if var is None:
            session.add(Kullanici(rol=Rol.admin, giris=giris, sifre_ozeti=sifre_ozeti(sifre)))
            mesaj = "E2E yöneticisi oluşturuldu."
        else:
            if var.rol != Rol.admin:
                print("Bu giriş yönetici olmayan bir hesaba ait.", file=sys.stderr)
                return 1
            var.sifre_ozeti = sifre_ozeti(sifre)
            var.aktif = True
            var.basarisiz_deneme = 0
            var.kilit_bitis = None
            mesaj = "E2E yöneticisinin şifresi güncellendi."
        await session.commit()
    print(mesaj)
    return 0


async def ornek_veri() -> int:
    """Geliştirme veritabanına örnek veri ekler (yalnızca ENV=dev)."""
    from app import ornek_veri as modul

    return await modul.yukle()


async def ornek_odeme_verisi() -> int:
    """Örnek öğrencilere paket ve ödeme ekler (yalnızca ENV=dev)."""
    from app import ornek_veri as modul

    return await modul.yukle_odeme()


def vapid_uret() -> int:
    """Web Push için VAPID anahtar çifti üretir ve .env satırlarını yazdırır (hiçbir yere kaydetmez)."""
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    def b64(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    anahtar = ec.generate_private_key(ec.SECP256R1())
    ozel = anahtar.private_numbers().private_value.to_bytes(32, "big")
    genel = anahtar.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    print(f"VAPID_PUBLIC_KEY={b64(genel)}")
    print(f"VAPID_PRIVATE_KEY={b64(ozel)}")
    print("VAPID_SUBJECT=mailto:kulup@example.com  # gerçek bir e-posta ile değiştirin")
    return 0


async def main() -> int:
    ayrac = argparse.ArgumentParser(prog="app.cli")
    alt = ayrac.add_subparsers(dest="komut", required=True)
    admin = alt.add_parser("admin-olustur", help="Yönetici hesabı oluşturur")
    admin.add_argument("giris", help="E-posta veya telefon")
    destek = alt.add_parser("destek-olustur", help="Teknik destek hesabı oluşturur (2FA ilk girişte kurulur)")
    destek.add_argument("giris", help="E-posta veya telefon")
    d2fa = alt.add_parser("destek-2fa-sifirla", help="Destek hesabının iki adımlı doğrulamasını sıfırlar")
    d2fa.add_argument("giris", help="Destek hesabının girişi")
    alt.add_parser("e2e-tohum", help="E2E test yöneticisini oluşturur (yalnız ENV=test|e2e)")
    alt.add_parser("ornek-veri", help="Geliştirme veritabanına örnek veri ekler (yalnız ENV=dev)")
    alt.add_parser("ornek-odeme-verisi", help="Örnek öğrencilere paket ve ödeme ekler (yalnız ENV=dev)")
    alt.add_parser("vapid-uret", help="Web Push için VAPID anahtar çifti üretir")
    argumanlar = ayrac.parse_args()

    try:
        if argumanlar.komut == "admin-olustur":
            return await admin_olustur(argumanlar.giris)
        if argumanlar.komut == "destek-olustur":
            return await destek_olustur(argumanlar.giris)
        if argumanlar.komut == "destek-2fa-sifirla":
            return await destek_2fa_sifirla(argumanlar.giris)
        if argumanlar.komut == "e2e-tohum":
            return await e2e_tohum()
        if argumanlar.komut == "ornek-veri":
            return await ornek_veri()
        if argumanlar.komut == "ornek-odeme-verisi":
            return await ornek_odeme_verisi()
        if argumanlar.komut == "vapid-uret":
            return vapid_uret()
        return 2
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
