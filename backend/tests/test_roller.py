import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.deps import rol_gerekli
from app.models import Rol
from tests.conftest import SIFRE, kullanici_olustur


@pytest_asyncio.fixture
async def rotali_istemci():
    """Yalnızca yönetici ve antrenöre açık deneme uç noktaları ekler. Üretim uygulamasına eklenmez."""
    deneme = FastAPI()

    @deneme.get("/yonetim", dependencies=[Depends(rol_gerekli(Rol.admin))])
    async def yonetim():
        return {"ok": True}

    @deneme.get("/ders", dependencies=[Depends(rol_gerekli(Rol.admin, Rol.antrenor))])
    async def ders():
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=deneme), base_url="https://test") as c:
        yield c


async def belirtec(istemci_ana, giris):
    yanit = await istemci_ana.post("/api/auth/login", json={"giris": giris, "sifre": SIFRE})
    return {"Authorization": f"Bearer {yanit.json()['access_token']}"}


async def test_rol_matrisi(istemci, rotali_istemci):
    await kullanici_olustur("admin@kulup.com", Rol.admin)
    await kullanici_olustur("antrenor@kulup.com", Rol.antrenor)
    await kullanici_olustur("veli@kulup.com", Rol.veli)

    admin = await belirtec(istemci, "admin@kulup.com")
    antrenor = await belirtec(istemci, "antrenor@kulup.com")
    veli = await belirtec(istemci, "veli@kulup.com")

    assert (await rotali_istemci.get("/yonetim", headers=admin)).status_code == 200
    assert (await rotali_istemci.get("/yonetim", headers=antrenor)).status_code == 403
    assert (await rotali_istemci.get("/yonetim", headers=veli)).status_code == 403

    assert (await rotali_istemci.get("/ders", headers=antrenor)).status_code == 200
    assert (await rotali_istemci.get("/ders", headers=veli)).status_code == 403


async def test_belirtecsiz_istek_401(rotali_istemci):
    assert (await rotali_istemci.get("/yonetim")).status_code == 401
