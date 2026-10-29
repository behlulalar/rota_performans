import pytest

from app.metin import baslik_yap
from tests.test_paketler import paket_olustur
from tests.test_gruplar import grup_olustur, yonetici  # noqa: F401
from tests.test_ogrenciler import GECERLI_TC


@pytest.mark.parametrize(
    "girdi,beklenen",
    [
        ("özel ders", "Özel Ders"),
        ("ÖZEL DERS", "Özel Ders"),
        ("  aylık   8 ders  ", "Aylık 8 Ders"),
        ("ışık İSMAİL", "Işık İsmail"),
        ("iLKAY ışıl", "İlkay Işıl"),
        ("ayşe-nur yılmaz", "Ayşe-Nur Yılmaz"),
        ("ali'nin", "Ali'nin"),
        ("u10 gençler", "U10 Gençler"),
        ("U12", "U12"),
        ("havuz ve spor", "Havuz ve Spor"),
        ("", ""),
    ],
)
def test_baslik_yap(girdi, beklenen):
    assert baslik_yap(girdi) == beklenen


async def test_paket_ve_grup_adi_baslik_yazimina_cevrilir(istemci, yonetici):
    p = await paket_olustur(istemci, yonetici, ad="özel ders")
    assert p["ad"] == "Özel Ders"
    r = await istemci.patch(f"/api/paketler/{p['id']}", json={"ad": "aylık ÇOCUK paketi"}, headers=yonetici)
    assert r.json()["ad"] == "Aylık Çocuk Paketi"
    g = await grup_olustur(istemci, yonetici, ad="yetişkin ıslak grubu")
    assert g["ad"] == "Yetişkin Islak Grubu"


async def test_ogrenci_ve_veli_isimleri_baslik_yazimina_cevrilir(istemci, yonetici):
    govde = {
        "ad": "ayşe nur", "soyad": "YILMAZ", "anne_adi": "fatma", "baba_adi": "mEHMET",
        "dogum_tarihi": "2015-05-10", "kimlik_tur": "tc", "kimlik_no": GECERLI_TC,
        "iletisim_kisileri": [{"rol": "diger", "ad_soyad": "fatma yılmaz", "telefon": "05321112233", "birincil": True}],
        "rizalar": {"aydinlatma": True, "foto": False, "whatsapp": False},
    }
    r = await istemci.post("/api/ogrenciler", json=govde, headers=yonetici)
    assert r.status_code == 201, r.text
    d = r.json()
    assert (d["ad"], d["soyad"], d["anne_adi"], d["baba_adi"]) == ("Ayşe Nur", "Yılmaz", "Fatma", "Mehmet")
    assert d["iletisim_kisileri"][0]["ad_soyad"] == "Fatma Yılmaz"
