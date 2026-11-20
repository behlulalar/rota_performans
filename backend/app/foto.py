"""Profil fotoğrafı işleme (öğrenci ve antrenör için ortak): doğrular, iki boyutta metadata'sız JPEG üretir."""
import io

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

FOTO_EN_COK_BAYT = 8 * 1024 * 1024
FOTO_FORMATLARI = {"JPEG", "PNG", "WEBP"}
BUYUK_KENAR = 800
KUCUK_KENAR = 160
JPEG_KALITE = 82
Image.MAX_IMAGE_PIXELS = 60_000_000


def foto_isle(veri: bytes) -> tuple[bytes, bytes]:
    """Resmi doğrular; metadata'sız, yönü düzeltilmiş iki JPEG üretir (buyuk, kucuk)."""
    try:
        with Image.open(io.BytesIO(veri)) as resim:
            if resim.format not in FOTO_FORMATLARI:
                raise ValueError
            resim.load()
            resim = ImageOps.exif_transpose(resim)
            if resim.mode in ("RGBA", "LA", "P"):
                resim = resim.convert("RGBA")
                zemin = Image.new("RGB", resim.size, (255, 255, 255))
                zemin.paste(resim, mask=resim.getchannel("A"))
                resim = zemin
            else:
                resim = resim.convert("RGB")
    except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, "Geçerli bir JPEG, PNG veya WebP resmi yükleyin")

    def kodla(r: Image.Image) -> bytes:
        cikti = io.BytesIO()
        # Yeni bir Image olduğundan EXIF/ICC vb. taşınmaz; exif parametresi de verilmez.
        r.save(cikti, "JPEG", quality=JPEG_KALITE, optimize=True)
        return cikti.getvalue()

    buyuk = resim.copy()
    buyuk.thumbnail((BUYUK_KENAR, BUYUK_KENAR), Image.LANCZOS)
    kucuk = ImageOps.fit(resim, (KUCUK_KENAR, KUCUK_KENAR), Image.LANCZOS)
    return kodla(buyuk), kodla(kucuk)
