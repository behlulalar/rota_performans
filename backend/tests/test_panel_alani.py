import pyotp
import pytest
from redis.asyncio import Redis
from sqlalchemy import select, update

from app.config import settings
from app.db import SessionLocal
from app.models import DenetimKaydi, Kullanici, Rol
from app.panel_alani import host_paneli
from tests.conftest import SIFRE, destek_olustur, kullanici_olustur

GENEL_HATA = "Giriş bilgileri hatalı veya hesap geçici olarak kilitli."

VELI = {"host": "veli.rotaperformans.com"}
YONETIM = {"host": "yonetim.rotaperformans.com"}
ANTRENOR = {"host": "antrenor.rotaperformans.com"}
DESTEK = {"host": "destek.rotaperformans.com"}
DUZ = {"host": "rotaperformans.com"}


@pytest.mark.parametrize(
    "host,panel",
    [
        ("yonetim.rotaperformans.com", "yonetici"),
        ("veli.rotaperformans.com", "veli"),
        ("antrenor.rotaperformans.com", "antrenor"),
        ("destek.rotaperformans.com", "destek"),
        ("veli.localhost:5175", "veli"),
        ("YONETIM.RotaPerformans.com:443", "yonetici"),
        ("rotaperformans.com", None),
        ("rota.behlulalar.online", None),
        ("localhost", None),
        ("localhost:5175", None),
        ("test", None),
        ("veli", None),
        ("", None),
        (None, None),
        ("[::1]:8000", None),
        ("www.rotaperformans.com", None),
    ],
)
def test_host_paneli(host, panel):
    assert host_paneli(host) == panel


async def _giris(istemci, giris, baslik, panel=None):
    govde = {"giris": giris, "sifre": SIFRE}
    if panel is not None:
        govde["panel"] = panel
    return await istemci.post("/api/auth/login", json=govde, headers=baslik)


async def _yetki(yanit) -> dict:
    assert yanit.status_code == 200, yanit.text
    return {"Authorization": f"Bearer {yanit.json()['access_token']}"}


async def test_her_alan_adinda_yalniz_kendi_rolleri_girer(istemci):
    await kullanici_olustur("yonetici@kulup.com", Rol.admin)
    await kullanici_olustur("hoca@kulup.com", Rol.antrenor)
    await kullanici_olustur("+905551112233", Rol.veli)
    await kullanici_olustur("ogrenci@kulup.com", Rol.ogrenci)

    for giris, baslik in [
        ("yonetici@kulup.com", YONETIM), ("hoca@kulup.com", ANTRENOR),
        ("+905551112233", VELI), ("ogrenci@kulup.com", VELI),
    ]:
        assert (await _giris(istemci, giris, baslik)).status_code == 200, (giris, baslik)
    for giris, baslik in [
        ("yonetici@kulup.com", VELI), ("yonetici@kulup.com", DESTEK), ("hoca@kulup.com", YONETIM),
        ("+905551112233", ANTRENOR), ("ogrenci@kulup.com", YONETIM),
    ]:
        yanit = await _giris(istemci, giris, baslik)
        assert yanit.status_code == 401 and yanit.json()["detail"] == GENEL_HATA, (giris, baslik)
    async with SessionLocal() as session:
        nedenler = {
            k.detay["neden"]
            for k in (
                await session.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "giris_basarisiz"))
            ).scalars()
        }
    assert nedenler == {"yanlis_panel"}


async def test_govdedeki_panel_alan_adiyla_celisirse_reddedilir(istemci):
    await kullanici_olustur("yonetici@kulup.com", Rol.admin)
    # Uyumlu gövde paneli sorun değil.
    assert (await _giris(istemci, "yonetici@kulup.com", YONETIM, panel="yonetici")).status_code == 200
    # Gövde "yonetici" dese de veli alan adında yönetici giremez; yönetim alan adında gövde "veli" diyemez.
    for baslik, panel in [(VELI, "yonetici"), (YONETIM, "veli")]:
        yanit = await _giris(istemci, "yonetici@kulup.com", baslik, panel=panel)
        assert yanit.status_code == 401 and yanit.json()["detail"] == GENEL_HATA
    async with SessionLocal() as session:
        log = (
            await session.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "giris_basarisiz"))
        ).scalars().first()
    assert log.detay["neden"] == "yanlis_panel"


async def test_belirtec_baska_alan_adinda_gecmez(istemci):
    await kullanici_olustur("+905551112233", Rol.veli)
    await kullanici_olustur("yonetici@kulup.com", Rol.admin)

    veli = await _yetki(await _giris(istemci, "+905551112233", VELI))
    assert (await istemci.get("/api/auth/me", headers={**veli, **VELI})).status_code == 200
    # Port ve büyük harf farkı aynı paneldir.
    assert (await istemci.get("/api/auth/me", headers={**veli, "host": "Veli.rotaperformans.com:443"})).status_code == 200
    for baslik in (YONETIM, DUZ, {"host": "test"}):
        assert (await istemci.get("/api/auth/me", headers={**veli, **baslik})).status_code == 401, baslik

    # Eşlenmeyen alan adında alınan belirteç panel alan adında geçmez.
    duz = await _yetki(await _giris(istemci, "yonetici@kulup.com", DUZ))
    assert (await istemci.get("/api/auth/me", headers={**duz, **DUZ})).status_code == 200
    assert (await istemci.get("/api/auth/me", headers=duz)).status_code == 200  # "test" de eşlenmez
    assert (await istemci.get("/api/auth/me", headers={**duz, **YONETIM})).status_code == 401


async def test_yenileme_alan_adi_paneliyle_belirtec_verir(istemci):
    await kullanici_olustur("yonetici@kulup.com", Rol.admin)
    assert (await _giris(istemci, "yonetici@kulup.com", YONETIM)).status_code == 200
    yeni = await _yetki(await istemci.post("/api/auth/refresh", headers=YONETIM))
    assert (await istemci.get("/api/auth/me", headers={**yeni, **YONETIM})).status_code == 200
    assert (await istemci.get("/api/auth/me", headers={**yeni, **VELI})).status_code == 401


async def test_yenileme_rol_alan_adina_uymuyorsa_reddedilir(istemci):
    k = await kullanici_olustur("yonetici@kulup.com", Rol.admin)
    assert (await _giris(istemci, "yonetici@kulup.com", YONETIM)).status_code == 200
    async with SessionLocal() as session:
        await session.execute(update(Kullanici).where(Kullanici.id == k.id).values(rol=Rol.antrenor))
        await session.commit()
    yanit = await istemci.post("/api/auth/refresh", headers=YONETIM)
    assert yanit.status_code == 401
    assert yanit.json()["detail"] == "Oturum süresi doldu, lütfen yeniden giriş yapın."


async def _kullanilan_kodlari_temizle():
    redis = Redis.from_url(settings.redis_url)
    async for anahtar in redis.scan_iter("2fa:kullanilan:*"):
        await redis.delete(anahtar)
    await redis.aclose()


async def test_destek_alan_adinda_ikili_dogrulamayla_girer(istemci):
    _, gizli = await destek_olustur()
    # Destek alan adında gövdede panel gerekmez.
    y = await _giris(istemci, "destek@kulup.com", DESTEK)
    assert y.status_code == 200, y.text
    bekleyen = y.json()["bekleyen_belirtec"]
    # 2. adım başka panelin alan adında tamamlanamaz.
    y = await istemci.post(
        "/api/auth/2fa/dogrula", json={"bekleyen_belirtec": bekleyen, "kod": pyotp.TOTP(gizli).now()}, headers=YONETIM
    )
    assert y.status_code == 401
    await _kullanilan_kodlari_temizle()
    y = await istemci.post(
        "/api/auth/2fa/dogrula", json={"bekleyen_belirtec": bekleyen, "kod": pyotp.TOTP(gizli).now()}, headers=DESTEK
    )
    yetki = await _yetki(y)
    assert (await istemci.get("/api/auth/me", headers={**yetki, **DESTEK})).status_code == 200
    assert (await istemci.get("/api/auth/me", headers={**yetki, **YONETIM})).status_code == 401
    # Destek hesabı yönetim alan adından giremez.
    yanit = await _giris(istemci, "destek@kulup.com", YONETIM)
    assert yanit.status_code == 401 and yanit.json()["detail"] == GENEL_HATA


async def test_kati_modda_eslenmeyen_alan_adi_421(istemci, monkeypatch):
    await kullanici_olustur("yonetici@kulup.com", Rol.admin)
    monkeypatch.setattr(settings, "panel_alani_kati", True)
    assert (await istemci.get("/api/saglik")).status_code == 200
    assert (await istemci.get("/api/saglik", headers=DUZ)).status_code == 200
    for baslik in ({"host": "test"}, DUZ, {"host": "rota.behlulalar.online"}):
        assert (await _giris(istemci, "yonetici@kulup.com", baslik)).status_code == 421, baslik
        assert (await istemci.get("/api/auth/me", headers=baslik)).status_code == 421, baslik
    assert (await _giris(istemci, "yonetici@kulup.com", YONETIM)).status_code == 200


async def _oturum_durumu():
    from app.models import Oturum

    async with SessionLocal() as session:
        return [(o.iptal, o.bitis) for o in (await session.execute(select(Oturum))).scalars()]


async def test_baska_alt_alan_adindan_cerezli_istekler_reddedilir(istemci):
    await kullanici_olustur("yonetici@kulup.com", Rol.admin)
    assert (await _giris(istemci, "yonetici@kulup.com", YONETIM)).status_code == 200
    once = await _oturum_durumu()
    yabanci = {**YONETIM, "origin": "https://veli.rotaperformans.com"}

    y = await istemci.post("/api/auth/refresh", headers=yabanci)
    assert y.status_code == 401
    assert y.json()["detail"] == "Oturum süresi doldu, lütfen yeniden giriş yapın."
    assert "set-cookie" not in y.headers  # çerez silinmez ve döndürülmez
    assert (await istemci.post("/api/auth/etkinlik", headers=yabanci)).status_code == 401
    y = await istemci.post("/api/auth/logout", headers=yabanci)
    assert y.status_code == 204 and "set-cookie" not in y.headers
    # Port farkı da başka kaynaktır.
    port = {**YONETIM, "origin": "https://yonetim.rotaperformans.com:8443"}
    assert (await istemci.post("/api/auth/refresh", headers=port)).status_code == 401
    assert await _oturum_durumu() == once  # oturum ne iptal edildi ne uzatıldı

    # Aynı kaynak (şema önemsiz) ve Origin'siz istek çalışır.
    ayni = {**YONETIM, "origin": "http://YONETIM.rotaperformans.com"}
    assert (await istemci.post("/api/auth/etkinlik", headers=ayni)).status_code == 204
    assert (await istemci.post("/api/auth/refresh", headers=ayni)).status_code == 200
    assert (await istemci.post("/api/auth/refresh", headers=YONETIM)).status_code == 200
    y = await istemci.post("/api/auth/logout", headers=ayni)
    assert y.status_code == 204 and "set-cookie" in y.headers
    assert (await istemci.post("/api/auth/refresh", headers=YONETIM)).status_code == 401


async def test_eslenmeyen_alan_adinda_origin_denetimi_yok(istemci):
    await kullanici_olustur("yonetici@kulup.com", Rol.admin)
    assert (await _giris(istemci, "yonetici@kulup.com", {"host": "test"})).status_code == 200
    y = await istemci.post("/api/auth/refresh", headers={"origin": "https://baska.example"})
    assert y.status_code == 200
