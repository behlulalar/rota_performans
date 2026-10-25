import pytest

from app import telefon
from app.security import normalize_giris

KANONIK = "+905321234567"


@pytest.mark.parametrize(
    "girdi",
    [
        "+905321234567",
        "905321234567",
        "05321234567",
        "5321234567",
        "0532 123 45 67",
        "0 (532) 123-45 67",
        "+90 (532) 123 45 67",
        "532-123-45-67",
    ],
)
def test_normalize_varyantlari(girdi):
    assert telefon.normalize(girdi) == KANONIK


@pytest.mark.parametrize(
    "girdi",
    ["", "abc", "532123456", "53212345678", "9053212345678", "+9053212345678", "05321234", "532 123 45 6a", "++905321234567", "+90"],
)
def test_normalize_reddeder(girdi):
    with pytest.raises(ValueError, match="10 haneden"):
        telefon.normalize(girdi)


def test_giris_icin():
    assert telefon.giris_icin("0532 123 45 67") == KANONIK
    assert telefon.giris_icin("abc") is None
    assert telefon.giris_icin("12345") is None


def test_normalize_giris():
    for g in ("0532 123 45 67", "532 123 45 67", "+90 532 123 45 67", " 905321234567 "):
        assert normalize_giris(g) == KANONIK
    assert normalize_giris(" Ali@Kulup.com ") == "ali@kulup.com"
    assert normalize_giris("12 34") == "1234"  # çözümlenemeyen: eski davranış
