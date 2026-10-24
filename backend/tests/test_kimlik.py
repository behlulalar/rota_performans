import pytest

from app import kimlik

# Algoritmaya uyan, kimseye ait olmayan örnek numaralar (üretilmiş test değerleri).
GECERLI = "10000000146"


def test_tc_algoritmasi():
    assert kimlik.tc_gecerli_mi(GECERLI)
    assert kimlik.tc_gecerli_mi(" 100 000 001 46 ")
    assert not kimlik.tc_gecerli_mi("10000000147")  # son hane yanlış
    assert not kimlik.tc_gecerli_mi("00000000000")
    assert not kimlik.tc_gecerli_mi("1234567890")  # 10 hane
    assert not kimlik.tc_gecerli_mi("1000000014a")
    assert not kimlik.tc_gecerli_mi("")


def test_sifrele_coz_gidis_donus():
    sifreli = kimlik.sifrele(GECERLI)
    assert GECERLI.encode() not in sifreli
    assert kimlik.coz(sifreli) == GECERLI


def test_ayni_numara_her_seferinde_farkli_sifrelenir_ama_ozeti_sabittir():
    a, b = kimlik.sifrele(GECERLI), kimlik.sifrele(GECERLI)
    assert a != b
    assert kimlik.ozet(GECERLI) == kimlik.ozet(" 100 000 001 46 ")
    assert kimlik.ozet(GECERLI) != kimlik.ozet("10000000147")
    assert GECERLI not in kimlik.ozet(GECERLI)


def test_bozulmus_veri_cozulemez():
    sifreli = bytearray(kimlik.sifrele(GECERLI))
    sifreli[-1] ^= 1
    with pytest.raises(kimlik.KimlikHatasi):
        kimlik.coz(bytes(sifreli))


def test_maskeleme():
    assert kimlik.maskele(GECERLI) == "100******46"
    assert GECERLI not in kimlik.maskele(GECERLI)
