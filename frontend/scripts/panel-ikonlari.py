"""Panel simgelerini üretir (Pillow + numpy): public/ altındaki veli simgelerinden zemin rengi değiştirilir.
Kullanım: python3 frontend/scripts/panel-ikonlari.py   (frontend/ içinden: python3 scripts/panel-ikonlari.py)
Şema "A - zemin rengi": yönetim = koyu amblem altın degrade üzerinde; antrenör = altın amblem lacivert; destek = altın amblem grafit.
"""
import os
import numpy as np
from PIL import Image

PUBLIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")
BG = np.array([13, 13, 14.0])
GOLD = np.array([212, 175, 55.0])

# (kaynak dosya, hedef dosya öneki, hedef sonek) -> icon-192.png => icon-192-<panel>.png gibi
KAYNAKLAR = [
    ("icon-192.png", "icon-{p}-192.png"),
    ("icon-512.png", "icon-{p}-512.png"),
    ("icon-maskable-512.png", "icon-maskable-{p}-512.png"),
    ("apple-touch-icon.png", "apple-touch-icon-{p}.png"),
    ("favicon.png", "favicon-{p}.png"),
]


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def yeni_zemin(boyut, panel):
    h, w = boyut
    if panel == "yonetim":  # köşegen altın degrade
        yy, xx = np.mgrid[0:h, 0:w]
        t = ((xx + yy) / float(w + h - 2))[..., None]
        return np.array([240, 205, 100.0]) * (1 - t) + np.array([176, 138, 38.0]) * t
    renk = hexc("#0b2340") if panel == "antrenor" else hexc("#34373c")
    return np.ones((h, w, 3)) * renk


def donustur(img, panel):
    a = np.asarray(img.convert("RGB")).astype(float)
    d = np.abs(a - BG).max(axis=2)
    ref = np.percentile(d[d > 40], 85)
    alpha = np.clip(d / ref, 0, 1)
    zemin = yeni_zemin(a.shape[:2], panel)
    if panel == "yonetim":
        al = np.clip(alpha * 1.15, 0, 1)[..., None]
        out = zemin * (1 - al) + BG * al  # amblem koyu
    else:
        al = alpha[..., None]
        renk = np.clip((a - BG * (1 - al)) / np.maximum(al, 1e-3), 0, 255)
        renk = np.where(al < 0.02, GOLD, renk)
        out = zemin * (1 - al) + renk * al
    return Image.fromarray(out.astype("uint8"))


for panel in ("yonetim", "antrenor", "destek"):
    for kaynak, hedef in KAYNAKLAR:
        src = Image.open(os.path.join(PUBLIC, kaynak))
        sonuc = donustur(src, panel)
        if src.mode == "RGBA":
            sonuc = sonuc.convert("RGBA")
        sonuc.save(os.path.join(PUBLIC, hedef.format(p=panel)), optimize=True)
        print(hedef.format(p=panel))
