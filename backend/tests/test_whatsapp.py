"""WhatsApp bağlantısı: Evolution API sahte sunucuyla (httpx.MockTransport) taklit edilir."""
import httpx
import pytest
from sqlalchemy import select

from app import whatsapp as wa
from app.config import settings
from app.db import SessionLocal
from app.models import DenetimKaydi, Rol
from tests.test_yoklama import giris, yonetici  # noqa: F401  (fixture)

URL = "/api/whatsapp"
DEVRE_YOK = {"devre_kesici": {"acik": False, "sebep": None}, "bekleyen_sayisi": 0}


class SahteEvolution:
    """Tek instance'lı Evolution: create -> connecting (QR), telefonda okutulunca open."""

    def __init__(self):
        self.durum: str | None = None  # None: instance yok
        self.istekler: list[str] = []
        self.coktu = False

    def __call__(self, r: httpx.Request) -> httpx.Response:
        if self.coktu:
            raise httpx.ConnectError("kapalı")
        assert r.headers["apikey"] == "gizli"
        yol = r.url.path
        self.istekler.append(f"{r.method} {yol}")
        yok = httpx.Response(404, json={"status": 404})
        if yol == "/instance/fetchInstances":
            if self.durum is None:
                return yok
            jid = "905321234567@s.whatsapp.net" if self.durum == "open" else None
            return httpx.Response(200, json=[{"name": "rota", "connectionStatus": self.durum, "ownerJid": jid, "profileName": "Rota Kulüp" if jid else None}])
        if yol == "/instance/connectionState/rota":
            return yok if self.durum is None else httpx.Response(200, json={"instance": {"state": self.durum}})
        if yol == "/instance/create":
            self.durum = "connecting"
            return httpx.Response(201, json={"instance": {"status": "connecting"}})
        if yol == "/instance/connect/rota":
            return httpx.Response(200, json={} if self.durum == "open" else {"base64": "data:image/png;base64,QR"})
        if yol == "/instance/logout/rota":
            return httpx.Response(400 if self.durum != "open" else 200, json={})
        if yol == "/instance/delete/rota":
            self.durum = None
            return httpx.Response(200, json={})
        return yok


@pytest.fixture
def evolution(monkeypatch):
    sahte = SahteEvolution()
    monkeypatch.setattr(settings, "evolution_url", "http://evolution:8080")
    monkeypatch.setattr(settings, "evolution_api_key", "gizli")
    monkeypatch.setattr(settings, "evolution_instance", "rota")
    monkeypatch.setattr(
        wa, "_istemci",
        lambda: httpx.AsyncClient(base_url="http://evolution:8080", headers={"apikey": "gizli"}, transport=httpx.MockTransport(sahte)),
    )
    return sahte


async def test_yapilandirilmamis(istemci, yonetici):
    assert (await istemci.get(URL, headers=yonetici)).json()["durum"] == "yapilandirilmadi"
    assert (await istemci.post(f"{URL}/baglan", headers=yonetici)).json()["durum"] == "yapilandirilmadi"
    assert (await istemci.post(f"{URL}/kes", headers=yonetici)).status_code == 409


async def test_qr_ile_baglanma_ve_kesme(istemci, yonetici, evolution):
    assert (await istemci.get(URL, headers=yonetici)).json() == {"durum": "bagli_degil", "numara": None, "profil_adi": None, "qr": None, **DEVRE_YOK}
    y = (await istemci.post(f"{URL}/baglan", headers=yonetici)).json()
    assert y["durum"] == "baglaniyor" and y["qr"] == "data:image/png;base64,QR"
    assert "POST /instance/create" in evolution.istekler
    # QR yenilenir; instance ikinci kez oluşturulmaz.
    await istemci.post(f"{URL}/baglan", headers=yonetici)
    assert evolution.istekler.count("POST /instance/create") == 1

    evolution.durum = "open"  # telefonda okutuldu
    y = (await istemci.get(URL, headers=yonetici)).json()
    assert y == {"durum": "bagli", "numara": "+905321234567", "profil_adi": "Rota Kulüp", "qr": None, **DEVRE_YOK}
    assert (await istemci.post(f"{URL}/baglan", headers=yonetici)).json()["durum"] == "bagli"

    y = await istemci.post(f"{URL}/kes", headers=yonetici)
    assert y.status_code == 200 and y.json()["durum"] == "bagli_degil"
    async with SessionLocal() as s:
        k = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "whatsapp_baglantisi_kesildi"))).scalar_one()
        assert k.detay == {"numara": "+905321234567"}


async def test_bekleyen_qr_iptal_edilebilir(istemci, yonetici, evolution):
    await istemci.post(f"{URL}/baglan", headers=yonetici)
    y = await istemci.post(f"{URL}/kes", headers=yonetici)
    assert y.status_code == 200 and evolution.durum is None


async def test_servis_kapali(istemci, yonetici, evolution):
    evolution.coktu = True
    assert (await istemci.get(URL, headers=yonetici)).json()["durum"] == "ulasilamiyor"
    assert (await istemci.post(f"{URL}/baglan", headers=yonetici)).json()["durum"] == "ulasilamiyor"
    assert (await istemci.post(f"{URL}/kes", headers=yonetici)).status_code == 502


async def test_yetki(istemci, evolution):
    assert (await istemci.get(URL)).status_code == 401
    for rol, eposta in ((Rol.antrenor, "a@kulup.com"), (Rol.veli, "v@kulup.com")):
        baslik = await giris(istemci, eposta, rol)
        assert (await istemci.get(URL, headers=baslik)).status_code == 403
        assert (await istemci.post(f"{URL}/baglan", headers=baslik)).status_code == 403
    assert evolution.istekler == []
