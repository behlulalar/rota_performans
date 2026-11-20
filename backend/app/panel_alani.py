"""Panel alt alan adları: her panel kendi alt alan adından sunulur (veli., yonetim., antrenor., destek.).

Giriş ve oturum, isteğin geldiği alan adının paneline bağlanır. Eşlenmeyen alan adları
(yerel geliştirme, testler, demo sunucusu) bugünkü birleşik davranışı korur.
"""

from fastapi import Request

# İlk DNS etiketi -> panel adı (auth.PANEL_ROLLERI anahtarları).
ALT_ALAN_PANELLERI = {
    "veli": "veli",
    "yonetim": "yonetici",
    "antrenor": "antrenor",
    "destek": "destek",
}


def host_paneli(host: str | None) -> str | None:
    """Host başlığından paneli çıkarır: port atılır, küçük harfe çevrilir, ilk etiket eşlenir.
    En az iki etiket gerekir; `localhost`, `test` gibi tek etiketli adlar eşlenmez."""
    if not host:
        return None
    ad = host.strip().lower()
    if ad.startswith("["):  # IPv6 adresi: panel yok
        return None
    ad = ad.split(":", 1)[0].rstrip(".")
    etiketler = ad.split(".")
    if len(etiketler) < 2:
        return None
    return ALT_ALAN_PANELLERI.get(etiketler[0])


def istek_paneli(request: Request) -> str | None:
    """Geçerli isteğin alan adına göre paneli (FastAPI bağımlılığı)."""
    return host_paneli(request.headers.get("host"))
