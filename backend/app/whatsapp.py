"""WhatsApp bağlantısı (Evolution API v2). Kulübün tek numarası tek bir "instance" olarak tutulur
(adı EVOLUTION_INSTANCE). Bu modül yalnız bağlantıyı yönetir: durum, QR ile bağlama, bağlantıyı kesme.
Mesaj gönderimi (`metin_gonder`) burada, ban koruması ve kuyruk mantığı app/whatsapp_gonder.py'dedir
(docs/bildirim-kurallari.md bölüm 4)."""
from dataclasses import dataclass
from typing import Literal

import httpx

from app.config import settings

Durum = Literal["yapilandirilmadi", "ulasilamiyor", "bagli_degil", "baglaniyor", "bagli"]
# Evolution'ın connectionStatus değerleri: open / connecting / close
_DURUMLAR: dict[str, Durum] = {"open": "bagli", "connecting": "baglaniyor", "close": "bagli_degil"}


class WhatsAppHatasi(Exception):
    """Evolution API'ye ulaşılamadı ya da beklenmeyen yanıt verdi."""


class KesinHata(WhatsAppHatasi):
    """Mesaj kesinlikle gitmedi (bağlantı kurulamadı ya da servis isteği reddetti): sonra yeniden denenebilir."""


class BelirsizSonuc(WhatsAppHatasi):
    """İstek gitmiş olabilir ama yanıt alınamadı (zaman aşımı, kopma, 5xx): mesaj gitmiş olabilir,
    bu yüzden YENİDEN DENENMEZ (çift mesaj olmasın)."""


class GecersizNumara(WhatsAppHatasi):
    """Numara WhatsApp'ta yok / geçersiz: yeniden denemenin anlamı yok."""


@dataclass
class Baglanti:
    durum: Durum
    numara: str | None = None  # "+905321234567"
    profil_adi: str | None = None
    qr: str | None = None  # data:image/png;base64,... (yalnız bağlanırken)


def _istemci() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.evolution_url.rstrip("/"), headers={"apikey": settings.evolution_api_key}, timeout=15
    )


async def _iste(yontem: str, yol: str, **kw) -> httpx.Response | None:
    """İsteği yapar; 404'te None döner (instance yok), diğer hatalarda WhatsAppHatasi."""
    try:
        async with _istemci() as c:
            y = await c.request(yontem, yol, **kw)
    except httpx.HTTPError as e:
        raise WhatsAppHatasi(f"Evolution API'ye ulaşılamadı: {e.__class__.__name__}") from e
    if y.status_code == 404:
        return None
    if y.status_code >= 400:
        raise WhatsAppHatasi(f"Evolution API hata döndü ({y.status_code})")
    return y


def _numara(owner_jid: str | None) -> str | None:
    # "905321234567@s.whatsapp.net" -> "+905321234567"
    if not owner_jid:
        return None
    rakam = owner_jid.split("@")[0].split(":")[0]
    return f"+{rakam}" if rakam.isdigit() else None


async def durum() -> Baglanti:
    if not settings.whatsapp_etkin:
        return Baglanti("yapilandirilmadi")
    try:
        y = await _iste("GET", "/instance/fetchInstances", params={"instanceName": settings.evolution_instance})
    except WhatsAppHatasi:
        return Baglanti("ulasilamiyor")
    liste = y.json() if y is not None else []
    if not liste:
        return Baglanti("bagli_degil")
    i = liste[0]
    d = _DURUMLAR.get(i.get("connectionStatus") or "", "bagli_degil")
    if d != "bagli":
        return Baglanti(d)
    return Baglanti("bagli", numara=_numara(i.get("ownerJid")), profil_adi=i.get("profileName"))


async def baglan() -> Baglanti:
    """Instance yoksa oluşturur, bağlı değilse yeni QR döner. Zaten bağlıysa durumu döner."""
    mevcut = await durum()
    if mevcut.durum in ("yapilandirilmadi", "ulasilamiyor", "bagli"):
        return mevcut
    ad = settings.evolution_instance
    if await _iste("GET", f"/instance/connectionState/{ad}") is None:
        await _iste("POST", "/instance/create", json={"instanceName": ad, "qrcode": True, "integration": "WHATSAPP-BAILEYS"})
    y = await _iste("GET", f"/instance/connect/{ad}")
    qr = (y.json() if y is not None else {}).get("base64")
    if not qr:
        # QR yoksa oturum bu arada açılmış olabilir.
        return await durum()
    return Baglanti("baglaniyor", qr=qr)


async def baglantiyi_kes() -> None:
    """Telefondaki oturumu kapatır ve instance'ı siler: sonraki bağlanma temiz bir QR ile başlar."""
    ad = settings.evolution_instance
    try:
        await _iste("DELETE", f"/instance/logout/{ad}")
    except WhatsAppHatasi:
        pass  # QR okutulmadan (bağlanırken) kesilen oturumda logout hata verir; silmek yeterli.
    await _iste("DELETE", f"/instance/delete/{ad}")


# Bağlantının hiç kurulamadığı hatalar: istek karşıya ulaşmadı, mesaj gitmedi.
_KESIN_AG_HATALARI = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


async def metin_gonder(numara: str, metin: str, gecikme_ms: int = 0) -> None:
    """Düz metin mesajı yollar (Evolution v2 `POST /message/sendText/{instance}`).
    `numara` ülke koduyla, yalnız rakam ("905321234567"); `+` varsa atılır. `gecikme_ms`: karşı tarafta
    "yazıyor…" göstergesinin süresi. Başarıda None döner; hatada KesinHata / BelirsizSonuc / GecersizNumara
    fırlatır. Hata iletilerine numara ve metin yazılmaz."""
    rakam = numara.lstrip("+")
    if not rakam.isdigit():
        raise GecersizNumara("Numara geçersiz")
    govde = {"number": rakam, "text": metin, "delay": max(0, int(gecikme_ms))}
    try:
        async with _istemci() as c:
            y = await c.post(f"/message/sendText/{settings.evolution_instance}", json=govde)
    except _KESIN_AG_HATALARI as e:
        raise KesinHata(f"Evolution API'ye bağlanılamadı: {e.__class__.__name__}") from e
    except httpx.HTTPError as e:
        raise BelirsizSonuc(f"Gönderim sonucu alınamadı: {e.__class__.__name__}") from e
    if y.status_code < 300:
        return
    if y.status_code == 400:
        raise GecersizNumara("Numara WhatsApp'ta bulunamadı")
    if y.status_code < 500:  # 401/403/404...: yapılandırma ya da oturum sorunu, istek işlenmedi
        raise KesinHata(f"Evolution API isteği reddetti ({y.status_code})")
    raise BelirsizSonuc(f"Evolution API hata döndü ({y.status_code})")
