"""Yönetim komutları.

Örnek:
    docker compose run --rm backend python -m app.cli admin-olustur ornek@kulup.com
"""
import argparse
import asyncio
import getpass
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models.kullanici import Kullanici, Rol
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
    elif not giris.lstrip("+").isdigit():
        print("Giriş bir e-posta adresi veya telefon numarası olmalı.", file=sys.stderr)
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


async def main() -> int:
    ayrac = argparse.ArgumentParser(prog="app.cli")
    alt = ayrac.add_subparsers(dest="komut", required=True)
    admin = alt.add_parser("admin-olustur", help="Yönetici hesabı oluşturur")
    admin.add_argument("giris", help="E-posta veya telefon")
    argumanlar = ayrac.parse_args()

    try:
        if argumanlar.komut == "admin-olustur":
            return await admin_olustur(argumanlar.giris)
        return 2
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
