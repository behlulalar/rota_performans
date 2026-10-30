import os

# Ayarlar içe aktarma sırasında okunduğu için, uygulamadan önce test ortamına geçilir.
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["REDIS_URL"] = os.environ["TEST_REDIS_URL"]
os.environ["COOKIE_SECURE"] = "true"

import asyncio  # noqa: E402

import pyotp  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from redis.asyncio import Redis  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Kullanici, Rol  # noqa: E402
from app.security import sifre_ozeti  # noqa: E402

SIFRE = "Dogru-sifre-123"


@pytest.fixture(scope="session", autouse=True)
def sema_sifirla():
    """Oturum başında test şemasını modellerden baştan kurar, eski kalıntı şema testi yanıltmasın."""

    async def _sifirla():
        async with engine.begin() as baglanti:
            await baglanti.run_sync(Base.metadata.drop_all)
            await baglanti.run_sync(Base.metadata.create_all)

    asyncio.run(_sifirla())


@pytest_asyncio.fixture(autouse=True)
async def temiz_ortam():
    async with engine.begin() as baglanti:
        await baglanti.run_sync(Base.metadata.create_all)
    redis = Redis.from_url(settings.redis_url)
    await redis.flushdb()
    await redis.aclose()
    yield
    async with engine.begin() as baglanti:
        tablolar = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        await baglanti.execute(text(f"TRUNCATE {tablolar} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def istemci():
    # https: Secure çerezlerin test istemcisinde saklanabilmesi için.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as c:
        yield c


async def kullanici_olustur(giris: str = "yonetici@kulup.com", rol: Rol = Rol.admin, aktif: bool = True) -> Kullanici:
    async with SessionLocal() as session:
        k = Kullanici(rol=rol, giris=giris, sifre_ozeti=sifre_ozeti(SIFRE), aktif=aktif)
        session.add(k)
        await session.commit()
        return k


async def destek_olustur(giris: str = "destek@kulup.com", totp: bool = True) -> tuple[Kullanici, str | None]:
    """Destek hesabı; totp=True ise 2FA kurulu (gizli anahtar döner), değilse kurulmamış."""
    from app import totp as totp_modulu

    gizli = pyotp.random_base32() if totp else None
    async with SessionLocal() as session:
        k = Kullanici(
            rol=Rol.destek, giris=giris, sifre_ozeti=sifre_ozeti(SIFRE), ad_soyad="Destek",
            totp_aktif=totp, totp_sifreli=totp_modulu.sifrele(gizli) if gizli else None,
            totp_kurtarma=[],
        )
        session.add(k)
        await session.commit()
        return k, gizli


async def destek_baslik(istemci, giris: str = "destek@kulup.com", gizli: str | None = None) -> dict:
    """Destek hesabını (yoksa oluşturup) gerçek akışla girdirir: şifre + panel, sonra TOTP kodu."""
    if gizli is None:
        _, gizli = await destek_olustur(giris)
    # Aynı zaman adımındaki kod tekrar kullanılamaz; testlerde art arda girişe izin vermek için işaretler temizlenir.
    redis = Redis.from_url(settings.redis_url)
    async for anahtar in redis.scan_iter("2fa:kullanilan:*"):
        await redis.delete(anahtar)
    await redis.aclose()
    y = await istemci.post("/api/auth/login", json={"giris": giris, "sifre": SIFRE, "panel": "destek"})
    assert y.status_code == 200, y.text
    bekleyen = y.json()["bekleyen_belirtec"]
    y = await istemci.post(
        "/api/auth/2fa/dogrula", json={"bekleyen_belirtec": bekleyen, "kod": pyotp.TOTP(gizli).now()}
    )
    assert y.status_code == 200, y.text
    return {"Authorization": f"Bearer {y.json()['access_token']}"}
