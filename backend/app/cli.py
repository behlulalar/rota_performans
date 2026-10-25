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
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal, engine
from app.models.kullanici import Kullanici, Rol
from app import telefon
from app.security import normalize_giris, sifre_ozeti

MIN_SIFRE_UZUNLUK = 12


async def admin_olustur(giris: str) -> int:
    giris = normalize_giris(giris)
    if "@" in giris:
        try:
            validate_email(giris, check_deliverability=False)
        except EmailNotValidError as hata:
            print(f"Geçersiz e-posta adresi: {hata}", file=sys.stderr)
            return 1
    elif telefon.giris_icin(giris) is None:
        print("Giriş bir e-posta adresi veya +90 ardından 10 haneli telefon numarası olmalı.", file=sys.stderr)
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

    async with SessionLocal() as session:
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


async def main() -> int:
    ayrac = argparse.ArgumentParser(prog="app.cli")
    alt = ayrac.add_subparsers(dest="komut", required=True)
    admin = alt.add_parser("admin-olustur", help="Yönetici hesabı oluşturur")
    admin.add_argument("giris", help="E-posta veya telefon")
    alt.add_parser("e2e-tohum", help="E2E test yöneticisini oluşturur (yalnız ENV=test|e2e)")
    argumanlar = ayrac.parse_args()

    try:
        if argumanlar.komut == "admin-olustur":
            return await admin_olustur(argumanlar.giris)
        if argumanlar.komut == "e2e-tohum":
            return await e2e_tohum()
        return 2
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
