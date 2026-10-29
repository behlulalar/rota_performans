import asyncio
import io
import re
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit, ders_hakki, kimlik
from app import telefon as telefon_modulu
from app.db import get_session
from app.depolama import depolama
from app.deps import rol_gerekli
from app.api.antrenorler import _giris_hazirla, _oturumlari_iptal_et, gecici_sifre_uret
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import (
    IletisimKisisi,
    IletisimRolu,
    KimlikTur,
    Ogrenci,
    OgrenciDurum,
    Riza,
    RizaTuru,
)
from app.models.program import DersOturumu, Grup, OgrenciGrup
from app.models.yoklama import DersHakkiHareketi, HareketTuru, Yoklama
from app.schemas.ogrenci import (
    BirincilIletisim,
    FotoBoyut,
    HesapAcGirdi,
    HesapAcYanit,
    HesapBilgi,
    IletisimKisisiGirdi,
    KimlikYanit,
    OgrenciDetay,
    OgrenciGuncelle,
    OgrenciListe,
    OgrenciOlustur,
    OgrenciOzet,
    ResitGecisiGirdi,
    ResitUyari,
    DersHakki,
)
from app.schemas.antrenor import SifreSifirlaYanit
from app.schemas.oturum import DersHakkiYanit, DuzeltmeGirdi, HareketOturum, HareketYanit
from app.security import sifre_ozeti

router = APIRouter(prefix="/api/ogrenciler", tags=["ogrenciler"])

FOTO_EN_COK_BAYT = 8 * 1024 * 1024
FOTO_FORMATLARI = {"JPEG", "PNG", "WEBP"}
BUYUK_KENAR = 800
KUCUK_KENAR = 160
JPEG_KALITE = 82
Image.MAX_IMAGE_PIXELS = 60_000_000

_PASAPORT = re.compile(r"^[A-Z0-9]{5,20}$")
GECERSIZ_TC = "Geçersiz T.C. kimlik numarası"
KIMLIK_TEKRAR = "Bu kimlik numarasıyla kayıtlı bir öğrenci var"

Yonetici = Depends(rol_gerekli(Rol.admin))


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _hata422(mesaj: str) -> HTTPException:
    return HTTPException(422, mesaj)


def _yas(dogum: date) -> int:
    bugun = date.today()
    return bugun.year - dogum.year - ((bugun.month, bugun.day) < (dogum.month, dogum.day))


def _telefon_normalize(telefon: str) -> str:
    try:
        return telefon_modulu.normalize(telefon)
    except ValueError as hata:
        raise _hata422(str(hata))


def _telefon_hazirla(telefon: str | None) -> str | None:
    """Boş/yalnız boşluk None sayılır; doluysa doğrulanıp normalize edilir."""
    if telefon is None or not telefon.strip():
        return None
    return _telefon_normalize(telefon)


def _kisileri_dogrula(kisiler: list[IletisimKisisiGirdi]) -> None:
    if sum(1 for k in kisiler if k.birincil) != 1:
        raise _hata422("Tam olarak bir birincil iletişim kişisi olmalı")
    if not any(k.rol in (IletisimRolu.diger, IletisimRolu.kendisi) for k in kisiler):
        raise _hata422("En az bir iletişim kişisinin rolü 'diger' veya 'kendisi' olmalı")


def _kimlik_hazirla(tur: KimlikTur, no: str | None) -> str | None:
    if no is None or not no.strip():
        return None
    n = kimlik.normalize(no)
    if tur == KimlikTur.tc:
        if not kimlik.tc_gecerli_mi(n):
            raise _hata422(GECERSIZ_TC)
    elif not _PASAPORT.fullmatch(n):
        raise _hata422("Pasaport numarası 5-20 harf veya rakamdan oluşmalı")
    return n


async def _ogrenci_al(session: AsyncSession, ogrenci_id: uuid.UUID) -> Ogrenci:
    ogrenci = await session.get(Ogrenci, ogrenci_id)
    if ogrenci is None or ogrenci.sentetik:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Öğrenci bulunamadı")
    return ogrenci


def _maskeli(ogrenci: Ogrenci) -> str | None:
    if ogrenci.kimlik_no_sifreli is None:
        return None
    return kimlik.maskele(kimlik.coz(ogrenci.kimlik_no_sifreli))


def _ozet(ogrenci: Ogrenci, birincil: IletisimKisisi | None) -> dict:
    return {
        "id": ogrenci.id,
        "ad": ogrenci.ad,
        "soyad": ogrenci.soyad,
        "dogum_tarihi": ogrenci.dogum_tarihi,
        "yas": _yas(ogrenci.dogum_tarihi),
        "durum": ogrenci.durum,
        "cinsiyet": ogrenci.cinsiyet,
        "kimlik_maskeli": _maskeli(ogrenci),
        "foto_var": ogrenci.foto_anahtar is not None,
        "telefon": ogrenci.telefon,
        "birincil_iletisim": BirincilIletisim(ad_soyad=birincil.ad_soyad, telefon=birincil.telefon, rol=birincil.rol)
        if birincil
        else None,
    }


async def _detay(session: AsyncSession, ogrenci: Ogrenci) -> OgrenciDetay:
    kisiler = list(
        (
            await session.execute(
                select(IletisimKisisi)
                .where(IletisimKisisi.ogrenci_id == ogrenci.id)
                .order_by(IletisimKisisi.olusturma, IletisimKisisi.id)
            )
        ).scalars()
    )
    rizalar = list(
        (await session.execute(select(Riza).where(Riza.ogrenci_id == ogrenci.id).order_by(Riza.verildi, Riza.id)))
        .scalars()
    )
    birincil = next((k for k in kisiler if k.birincil), None)
    yas = _yas(ogrenci.dogum_tarihi)
    uyarilar = []
    if yas < 5:
        uyarilar.append("Öğrenci 5 yaşını doldurmamış")
    if yas >= 18 and (birincil is None or birincil.rol != IletisimRolu.kendisi):
        uyarilar.append("Öğrenci reşit, birincil iletişim kişisi kendisi olmalı")
    gruplar = (
        await session.execute(
            select(Grup.id, Grup.ad)
            .join(OgrenciGrup, OgrenciGrup.grup_id == Grup.id)
            .where(OgrenciGrup.ogrenci_id == ogrenci.id, OgrenciGrup.bitis.is_(None))
            .order_by(Grup.ad, Grup.id)
        )
    ).all()
    hesap = None
    if birincil is not None and birincil.kullanici_id is not None:
        k = await session.get(Kullanici, birincil.kullanici_id)
        bagli = (
            await session.execute(
                select(func.count(func.distinct(IletisimKisisi.ogrenci_id))).where(
                    IletisimKisisi.kullanici_id == k.id
                )
            )
        ).scalar_one()
        hesap = HesapBilgi(giris=k.giris, rol=k.rol, aktif=k.aktif, bagli_ogrenci_sayisi=bagli)
    return OgrenciDetay(
        **_ozet(ogrenci, birincil),
        anne_adi=ogrenci.anne_adi,
        baba_adi=ogrenci.baba_adi,
        kimlik_tur=ogrenci.kimlik_tur,
        kayit_tarihi=ogrenci.kayit_tarihi,
        iletisim_kisileri=kisiler,
        rizalar=[{"tur": r.tur, "verildi": r.verildi, "geri_cekildi": r.geri_cekildi} for r in rizalar],
        uyarilar=uyarilar,
        gruplar=[{"id": g.id, "ad": g.ad} for g in gruplar],
        hesap=hesap,
        ders_hakki={
            **await ders_hakki.bakiye(session, ogrenci.id),
            "kullanilabilir_telafi": await ders_hakki.kullanilabilir_telafi(session, ogrenci.id),
        },
    )


async def _kimlik_tekrar_var_mi(session: AsyncSession, ozet: str, haric: uuid.UUID | None = None) -> bool:
    sorgu = select(Ogrenci.id).where(Ogrenci.kimlik_no_ozet == ozet)
    if haric is not None:
        sorgu = sorgu.where(Ogrenci.id != haric)
    return (await session.execute(sorgu)).first() is not None


def _kimlik_yaz(ogrenci: Ogrenci, tur: KimlikTur, no: str | None) -> None:
    ogrenci.kimlik_tur = tur
    ogrenci.kimlik_no_sifreli = kimlik.sifrele(no) if no else None
    ogrenci.kimlik_no_ozet = kimlik.ozet(no) if no else None


@router.post("/{ogrenci_id}/ders-hakki/duzeltme", response_model=DersHakki)
async def ders_hakki_duzelt(
    ogrenci_id: uuid.UUID,
    govde: DuzeltmeGirdi,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    await _ogrenci_al(session, ogrenci_id)
    session.add(
        DersHakkiHareketi(
            ogrenci_id=ogrenci_id,
            sayac=govde.sayac,
            miktar=govde.miktar,
            tur=HareketTuru.manuel_duzeltme,
            neden=govde.neden,
            olusturan_id=yonetici.id,
        )
    )
    # Neden metni kişisel veri içerebileceği için denetime yazılmaz.
    await audit.kaydet(
        session, "ders_hakki_duzeltildi", kullanici_id=yonetici.id, hedef_tur="ogrenci", hedef_id=str(ogrenci_id),
        ip=_ip(request), detay={"sayac": govde.sayac.value, "miktar": govde.miktar},
    )
    await session.commit()
    return await ders_hakki.bakiye(session, ogrenci_id)


@router.get("/{ogrenci_id}/ders-hakki", response_model=DersHakkiYanit)
async def ders_hakki_getir(
    ogrenci_id: uuid.UUID, _: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)
):
    await _ogrenci_al(session, ogrenci_id)
    bakiye = await ders_hakki.bakiye(session, ogrenci_id)
    # İptal satırlarında yoklama_id boştur, oturum bilgisi geri aldığı hareketin yoklamasından gelir.
    hedef = aliased(DersHakkiHareketi)
    satirlar = (
        await session.execute(
            select(DersHakkiHareketi, DersOturumu.tarih, Grup.ad)
            .outerjoin(hedef, hedef.id == DersHakkiHareketi.iptal_edilen_id)
            .outerjoin(Yoklama, Yoklama.id == func.coalesce(DersHakkiHareketi.yoklama_id, hedef.yoklama_id))
            .outerjoin(DersOturumu, DersOturumu.id == Yoklama.oturum_id)
            .outerjoin(Grup, Grup.id == DersOturumu.grup_id)
            .where(DersHakkiHareketi.ogrenci_id == ogrenci_id)
            .order_by(DersHakkiHareketi.zaman.desc(), DersHakkiHareketi.id.desc())
            .limit(100)
        )
    ).all()
    return DersHakkiYanit(
        **bakiye,
        hareketler=[
            HareketYanit(
                id=h.id, zaman=h.zaman, sayac=h.sayac, miktar=h.miktar, tur=h.tur, neden=h.neden,
                oturum=HareketOturum(tarih=tarih, grup_ad=grup_ad) if tarih is not None else None,
            )
            for h, tarih, grup_ad in satirlar
        ],
    )


@router.get("", response_model=OgrenciListe)
async def listele(
    q: str | None = Query(default=None, max_length=100),
    durum: OgrenciDurum | None = None,
    sayfa: int = Query(default=1, ge=1),
    boyut: int = Query(default=25, ge=1, le=100),
    _: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    kosullar = [Ogrenci.sentetik.is_(False)]
    if durum is not None:
        kosullar.append(Ogrenci.durum == durum)
    if q and q.strip():
        kacis = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        desen = f"%{kacis}%"
        kosullar.append(
            or_(
                Ogrenci.ad.ilike(desen, escape="\\"),
                Ogrenci.soyad.ilike(desen, escape="\\"),
                (Ogrenci.ad + " " + Ogrenci.soyad).ilike(desen, escape="\\"),
            )
        )
    toplam = (await session.execute(select(func.count()).select_from(Ogrenci).where(*kosullar))).scalar_one()
    ogrenciler = list(
        (
            await session.execute(
                select(Ogrenci)
                .where(*kosullar)
                .order_by(Ogrenci.soyad, Ogrenci.ad, Ogrenci.id)
                .limit(boyut)
                .offset((sayfa - 1) * boyut)
            )
        ).scalars()
    )
    birincil = {}
    if ogrenciler:
        satirlar = await session.execute(
            select(IletisimKisisi).where(
                IletisimKisisi.ogrenci_id.in_([o.id for o in ogrenciler]), IletisimKisisi.birincil.is_(True)
            )
        )
        birincil = {k.ogrenci_id: k for k in satirlar.scalars()}
    return OgrenciListe(
        kayitlar=[OgrenciOzet(**_ozet(o, birincil.get(o.id))) for o in ogrenciler],
        toplam=toplam,
        sayfa=sayfa,
        boyut=boyut,
    )


@router.post("", response_model=OgrenciDetay, status_code=status.HTTP_201_CREATED)
async def olustur(
    govde: OgrenciOlustur,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogr_telefon = _telefon_hazirla(govde.telefon)
    resit = _yas(govde.dogum_tarihi) >= 18
    if resit:
        if ogr_telefon is None:
            raise _hata422("Reşit öğrenci için öğrencinin kendi telefon numarası gerekli")
        # Birincil iletişim sunucuda üretilir; gelen "kendisi" satırları yok sayılır, diğerleri birincil olamaz.
        kisiler = [
            k.model_copy(update={"birincil": False})
            for k in govde.iletisim_kisileri
            if k.rol != IletisimRolu.kendisi
        ]
    else:
        kisiler = list(govde.iletisim_kisileri)
        _kisileri_dogrula(kisiler)
    no = _kimlik_hazirla(govde.kimlik_tur, govde.kimlik_no)
    telefonlar = [_telefon_normalize(k.telefon) for k in kisiler]
    if no and await _kimlik_tekrar_var_mi(session, kimlik.ozet(no)):
        raise HTTPException(status.HTTP_409_CONFLICT, KIMLIK_TEKRAR)

    ogrenci = Ogrenci(
        ad=govde.ad.strip(),
        soyad=govde.soyad.strip(),
        anne_adi=(govde.anne_adi or "").strip() or None,
        baba_adi=(govde.baba_adi or "").strip() or None,
        dogum_tarihi=govde.dogum_tarihi,
        cinsiyet=govde.cinsiyet,
        telefon=ogr_telefon,
        durum=OgrenciDurum.aktif,
    )
    _kimlik_yaz(ogrenci, govde.kimlik_tur, no)
    session.add(ogrenci)
    await session.flush()

    birincil_id = None
    if resit:
        kendisi = IletisimKisisi(
            id=uuid.uuid4(),
            ogrenci_id=ogrenci.id,
            rol=IletisimRolu.kendisi,
            ad_soyad=f"{ogrenci.ad} {ogrenci.soyad}",
            telefon=ogr_telefon,
            birincil=True,
            whatsapp_izni=govde.rizalar.whatsapp,
        )
        session.add(kendisi)
        await session.flush()
        birincil_id = kendisi.id
    for k, telefon in zip(kisiler, telefonlar):
        satir = IletisimKisisi(
            id=uuid.uuid4(),
            ogrenci_id=ogrenci.id,
            rol=k.rol,
            ad_soyad=k.ad_soyad.strip(),
            telefon=telefon,
            birincil=k.birincil,
            whatsapp_izni=k.birincil and govde.rizalar.whatsapp,
        )
        session.add(satir)
        if k.birincil:
            birincil_id = satir.id
    for tur in RizaTuru:
        if getattr(govde.rizalar, tur.value):
            session.add(Riza(ogrenci_id=ogrenci.id, iletisim_kisisi_id=birincil_id, tur=tur, kaydeden_id=yonetici.id))
    await audit.kaydet(
        session, "ogrenci_olusturuldu", kullanici_id=yonetici.id, hedef_tur="ogrenci", hedef_id=str(ogrenci.id),
        ip=_ip(request),
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, KIMLIK_TEKRAR)
    await session.refresh(ogrenci)
    return await _detay(session, ogrenci)


@router.get("/resit-uyarilari", response_model=list[ResitUyari])
async def resit_uyarilari(_: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
    bugun = date.today()
    satirlar = await session.execute(
        select(Ogrenci, IletisimKisisi)
        .outerjoin(
            IletisimKisisi, (IletisimKisisi.ogrenci_id == Ogrenci.id) & IletisimKisisi.birincil.is_(True)
        )
        .where(
            Ogrenci.sentetik.is_(False),
            Ogrenci.durum == OgrenciDurum.aktif,
            Ogrenci.dogum_tarihi <= date(bugun.year - 18, 12, 31),
        )
        .order_by(Ogrenci.soyad, Ogrenci.ad, Ogrenci.id)
    )
    return [
        ResitUyari(
            id=o.id, ad=o.ad, soyad=o.soyad, yas=_yas(o.dogum_tarihi),
            birincil_rol=b.rol if b else None, veli_hesabi_var=b is not None and b.kullanici_id is not None, telefon=o.telefon,
        )
        for o, b in satirlar.all()
        if _yas(o.dogum_tarihi) >= 18 and (b is None or b.rol != IletisimRolu.kendisi)
    ]


@router.get("/{ogrenci_id}", response_model=OgrenciDetay)
async def getir(ogrenci_id: uuid.UUID, _: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
    return await _detay(session, await _ogrenci_al(session, ogrenci_id))


@router.patch("/{ogrenci_id}", response_model=OgrenciDetay)
async def guncelle(
    ogrenci_id: uuid.UUID,
    govde: OgrenciGuncelle,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    verilen = govde.model_fields_set
    if ("kimlik_tur" in verilen) != ("kimlik_no" in verilen):
        raise _hata422("kimlik_tur ve kimlik_no birlikte gönderilmeli")
    for alan in ("ad", "soyad", "dogum_tarihi"):
        if alan in verilen and getattr(govde, alan) is None:
            raise _hata422(f"{alan} boş olamaz")
    if "kimlik_tur" in verilen and govde.kimlik_tur is None:
        raise _hata422("kimlik_tur boş olamaz")

    for alan in ("ad", "soyad", "anne_adi", "baba_adi"):
        if alan in verilen:
            deger = getattr(govde, alan)
            setattr(ogrenci, alan, deger.strip() or None if deger is not None else None)
    if "dogum_tarihi" in verilen:
        ogrenci.dogum_tarihi = govde.dogum_tarihi
    if "cinsiyet" in verilen:
        ogrenci.cinsiyet = govde.cinsiyet
    if "telefon" in verilen:
        yeni_tel = _telefon_hazirla(govde.telefon)
        kendisi_birincil = (
            await session.execute(
                select(IletisimKisisi)
                .where(
                    IletisimKisisi.ogrenci_id == ogrenci.id,
                    IletisimKisisi.rol == IletisimRolu.kendisi,
                    IletisimKisisi.birincil.is_(True),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if kendisi_birincil is not None:
            if yeni_tel is None:
                raise _hata422("Birincil iletişimi öğrencinin kendisi olan kayıtta telefon boş bırakılamaz")
            kendisi_birincil.telefon = yeni_tel
        ogrenci.telefon = yeni_tel
    if "kimlik_tur" in verilen:
        no = _kimlik_hazirla(govde.kimlik_tur, govde.kimlik_no)
        if no and await _kimlik_tekrar_var_mi(session, kimlik.ozet(no), haric=ogrenci.id):
            raise HTTPException(status.HTTP_409_CONFLICT, KIMLIK_TEKRAR)
        _kimlik_yaz(ogrenci, govde.kimlik_tur, no)
    await audit.kaydet(
        session, "ogrenci_guncellendi", kullanici_id=yonetici.id, hedef_tur="ogrenci", hedef_id=str(ogrenci.id),
        ip=_ip(request),
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, KIMLIK_TEKRAR)
    await session.refresh(ogrenci)
    return await _detay(session, ogrenci)


@router.put("/{ogrenci_id}/iletisim-kisileri", response_model=OgrenciDetay)
async def kisileri_degistir(
    ogrenci_id: uuid.UUID,
    kisiler: list[IletisimKisisiGirdi],
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    _kisileri_dogrula(kisiler)
    telefonlar = [_telefon_normalize(k.telefon) for k in kisiler]

    mevcut = list(
        (await session.execute(select(IletisimKisisi).where(IletisimKisisi.ogrenci_id == ogrenci.id).with_for_update()))
        .scalars()
    )
    # Gelen kişi önce id ile, yoksa aynı rol+telefon ile mevcut satıra eşlenir.
    eslesen: dict[int, IletisimKisisi] = {}
    kullanilan: set[uuid.UUID] = set()
    for i, (k, telefon) in enumerate(zip(kisiler, telefonlar)):
        aday = next((m for m in mevcut if k.id is not None and m.id == k.id and m.id not in kullanilan), None)
        if aday is None and k.id is None:
            aday = next(
                (m for m in mevcut if m.rol == k.rol and m.telefon == telefon and m.id not in kullanilan), None
            )
        if aday is not None:
            eslesen[i] = aday
            kullanilan.add(aday.id)
    hesapli = next((m for m in mevcut if m.birincil and m.kullanici_id is not None), None)
    if hesapli is not None and not any(k.birincil and eslesen.get(i) is hesapli for i, k in enumerate(kisiler)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Hesabı olan birincil kişi değiştirilemez (hesap devri henüz desteklenmiyor)"
        )

    whatsapp_riza = (
        await session.execute(
            select(Riza.id).where(
                Riza.ogrenci_id == ogrenci.id, Riza.tur == RizaTuru.whatsapp, Riza.geri_cekildi.is_(None)
            )
        )
    ).first() is not None

    for m in mevcut:
        if m.id not in kullanilan:
            await session.delete(m)
    await session.flush()
    # Tek birincil kısıtı için önce hepsi birincil olmaktan çıkarılır.
    for m in mevcut:
        # Hesaplı birincil kişi (yukarıda doğrulandı) birincil kalır: hesap yalnızca birincilde olabilir.
        if m.id in kullanilan and m.kullanici_id is None:
            m.birincil = False
    await session.flush()
    for i, (k, telefon) in enumerate(zip(kisiler, telefonlar)):
        satir = eslesen.get(i)
        if satir is None:
            satir = IletisimKisisi(ogrenci_id=ogrenci.id)
            session.add(satir)
        satir.rol = k.rol
        satir.ad_soyad = k.ad_soyad.strip()
        satir.telefon = telefon
        satir.birincil = k.birincil
        if k.birincil:
            satir.whatsapp_izni = whatsapp_riza
        elif satir.kullanici_id is None:
            satir.whatsapp_izni = False
    await audit.kaydet(
        session, "ogrenci_iletisim_degisti", kullanici_id=yonetici.id, hedef_tur="ogrenci",
        hedef_id=str(ogrenci.id), ip=_ip(request),
    )
    await session.commit()
    return await _detay(session, ogrenci)


async def _durum_degistir(
    ogrenci_id: uuid.UUID, durum: OgrenciDurum, islem: str, request: Request, yonetici: Kullanici, session: AsyncSession
) -> OgrenciDetay:
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    ogrenci.durum = durum
    if durum == OgrenciDurum.pasif:
        # Pasif öğrenci hiçbir grupta kalmaz, üyelikler bugün tarihiyle kapanır.
        await session.execute(
            update(OgrenciGrup)
            .where(OgrenciGrup.ogrenci_id == ogrenci.id, OgrenciGrup.bitis.is_(None))
            .values(bitis=func.current_date())
        )
    await audit.kaydet(
        session, islem, kullanici_id=yonetici.id, hedef_tur="ogrenci", hedef_id=str(ogrenci.id), ip=_ip(request)
    )
    await session.commit()
    return await _detay(session, ogrenci)


@router.post("/{ogrenci_id}/pasife-al", response_model=OgrenciDetay)
async def pasife_al(
    ogrenci_id: uuid.UUID, request: Request, yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    return await _durum_degistir(ogrenci_id, OgrenciDurum.pasif, "ogrenci_pasife_alindi", request, yonetici, session)


@router.post("/{ogrenci_id}/aktif-et", response_model=OgrenciDetay)
async def aktif_et(
    ogrenci_id: uuid.UUID, request: Request, yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    return await _durum_degistir(ogrenci_id, OgrenciDurum.aktif, "ogrenci_aktif_edildi", request, yonetici, session)


@router.get("/{ogrenci_id}/kimlik", response_model=KimlikYanit)
async def kimlik_getir(
    ogrenci_id: uuid.UUID, request: Request, yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    if ogrenci.kimlik_no_sifreli is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kimlik numarası kayıtlı değil")
    no = kimlik.coz(ogrenci.kimlik_no_sifreli)
    await audit.kaydet(
        session, "kimlik_goruntulendi", kullanici_id=yonetici.id, hedef_tur="ogrenci", hedef_id=str(ogrenci.id),
        ip=_ip(request),
    )
    await session.commit()
    return KimlikYanit(kimlik_no=no)


def _foto_isle(veri: bytes) -> tuple[bytes, bytes]:
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
        raise _hata422("Geçerli bir JPEG, PNG veya WebP resmi yükleyin")

    def kodla(r: Image.Image) -> bytes:
        cikti = io.BytesIO()
        # Yeni bir Image olduğundan EXIF/ICC vb. taşınmaz; exif parametresi de verilmez.
        r.save(cikti, "JPEG", quality=JPEG_KALITE, optimize=True)
        return cikti.getvalue()

    buyuk = resim.copy()
    buyuk.thumbnail((BUYUK_KENAR, BUYUK_KENAR), Image.LANCZOS)
    kucuk = ImageOps.fit(resim, (KUCUK_KENAR, KUCUK_KENAR), Image.LANCZOS)
    return kodla(buyuk), kodla(kucuk)


@router.post("/{ogrenci_id}/foto", status_code=status.HTTP_204_NO_CONTENT)
async def foto_yukle(
    ogrenci_id: uuid.UUID,
    request: Request,
    dosya: UploadFile = File(...),
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    riza = (
        await session.execute(
            select(Riza.id).where(
                Riza.ogrenci_id == ogrenci.id, Riza.tur == RizaTuru.foto, Riza.geri_cekildi.is_(None)
            )
        )
    ).first()
    if riza is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Fotoğraf için veli rızası yok")
    veri = await dosya.read(FOTO_EN_COK_BAYT + 1)
    if len(veri) > FOTO_EN_COK_BAYT:
        raise HTTPException(413, "Dosya en fazla 8 MB olabilir")
    buyuk, kucuk = await asyncio.to_thread(_foto_isle, veri)

    anahtar = uuid.uuid4().hex
    eski = ogrenci.foto_anahtar
    await asyncio.to_thread(depolama.kaydet, anahtar, "buyuk", buyuk)
    await asyncio.to_thread(depolama.kaydet, anahtar, "kucuk", kucuk)
    ogrenci.foto_anahtar = anahtar
    await audit.kaydet(
        session, "ogrenci_foto_yuklendi", kullanici_id=yonetici.id, hedef_tur="ogrenci", hedef_id=str(ogrenci.id),
        ip=_ip(request),
    )
    try:
        await session.commit()
    except Exception:
        await asyncio.to_thread(depolama.sil, anahtar)
        raise
    if eski:
        await asyncio.to_thread(depolama.sil, eski)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{ogrenci_id}/foto")
async def foto_getir(
    ogrenci_id: uuid.UUID,
    request: Request,
    boyut: FotoBoyut = "kucuk",
    _: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    veri = await asyncio.to_thread(depolama.oku, ogrenci.foto_anahtar, boyut) if ogrenci.foto_anahtar else None
    if veri is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fotoğraf bulunamadı")
    basliklar = {"Cache-Control": "private, max-age=86400", "ETag": f'"{ogrenci.foto_anahtar}-{boyut}"'}
    if request.headers.get("if-none-match") == basliklar["ETag"]:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=basliklar)
    return Response(content=veri, media_type="image/jpeg", headers=basliklar)


@router.delete("/{ogrenci_id}/foto", status_code=status.HTTP_204_NO_CONTENT)
async def foto_sil(
    ogrenci_id: uuid.UUID, request: Request, yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    eski = ogrenci.foto_anahtar
    if eski:
        ogrenci.foto_anahtar = None
        await audit.kaydet(
            session, "ogrenci_foto_silindi", kullanici_id=yonetici.id, hedef_tur="ogrenci",
            hedef_id=str(ogrenci.id), ip=_ip(request),
        )
        await session.commit()
        await asyncio.to_thread(depolama.sil, eski)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


HESAP_VAR = "Bu öğrencinin panel hesabı zaten var"
HESAP_YOK = "Öğrencinin panel hesabı yok"
GIRIS_BASKA_TUR = "Bu giriş bilgisi başka türde bir hesapta kayıtlı"


async def _birincil_al(session: AsyncSession, ogrenci: Ogrenci) -> IletisimKisisi | None:
    return (
        await session.execute(
            select(IletisimKisisi)
            .where(IletisimKisisi.ogrenci_id == ogrenci.id, IletisimKisisi.birincil.is_(True))
            .with_for_update()
        )
    ).scalar_one_or_none()


async def _hesabi_ayir(session: AsyncSession, ogrenci: Ogrenci, birincil: IletisimKisisi) -> None:
    """Hesabı bu öğrenciden ayırır; başka bağı kalmadıysa hesabı pasifleştirir ve oturumları iptal eder."""
    kullanici_id = birincil.kullanici_id
    birincil.kullanici_id = None
    if ogrenci.kullanici_id == kullanici_id:
        ogrenci.kullanici_id = None
    await session.flush()
    baska_kisi = (
        await session.execute(select(IletisimKisisi.id).where(IletisimKisisi.kullanici_id == kullanici_id).limit(1))
    ).first()
    baska_ogrenci = (
        await session.execute(select(Ogrenci.id).where(Ogrenci.kullanici_id == kullanici_id).limit(1))
    ).first()
    if baska_kisi is None and baska_ogrenci is None:
        kullanici = await session.get(Kullanici, kullanici_id)
        if kullanici is not None:
            kullanici.aktif = False
            await _oturumlari_iptal_et(session, kullanici.id)


@router.post("/{ogrenci_id}/hesap", response_model=HesapAcYanit)
async def hesap_ac(
    ogrenci_id: uuid.UUID,
    govde: HesapAcGirdi,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    if ogrenci.durum != OgrenciDurum.aktif:
        raise _hata422("Pasif öğrenci için panel hesabı açılamaz")
    birincil = await _birincil_al(session, ogrenci)
    if birincil is None:
        raise _hata422("Öğrencinin birincil iletişim kişisi yok")
    if birincil.kullanici_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, HESAP_VAR)
    giris = _giris_hazirla(govde.giris or birincil.telefon)
    rol = Rol.ogrenci if birincil.rol == IletisimRolu.kendisi else Rol.veli

    kullanici = (await session.execute(select(Kullanici).where(Kullanici.giris == giris))).scalar_one_or_none()
    sifre = None
    if kullanici is not None:
        if kullanici.rol != rol:
            raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_BASKA_TUR)
        if rol == Rol.ogrenci:
            # Öğrenci hesabı yalnız tek öğrenciye bağlanabilir.
            dolu = (
                await session.execute(
                    select(Ogrenci.id).where(Ogrenci.kullanici_id == kullanici.id, Ogrenci.id != ogrenci.id).limit(1)
                )
            ).first()
            if dolu is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_BASKA_TUR)
        kullanici.aktif = True
    else:
        sifre = gecici_sifre_uret()
        kullanici = Kullanici(rol=rol, giris=giris, sifre_ozeti=sifre_ozeti(sifre), ad_soyad=birincil.ad_soyad, aktif=True,
                            sifre_degistirmeli=True)
        session.add(kullanici)
        await session.flush()
    birincil.kullanici_id = kullanici.id
    if rol == Rol.ogrenci:
        ogrenci.kullanici_id = kullanici.id
    await audit.kaydet(
        session, "panel_hesabi_acildi" if sifre else "panel_hesabi_baglandi", kullanici_id=yonetici.id,
        hedef_tur="ogrenci", hedef_id=str(ogrenci.id), ip=_ip(request), detay={"rol": rol.value},
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu giriş bilgisi başka bir hesapta kayıtlı")
    return HesapAcYanit(giris=giris, gecici_sifre=sifre, yeni_hesap=sifre is not None)


@router.delete("/{ogrenci_id}/hesap", response_model=OgrenciDetay)
async def hesap_ayir(
    ogrenci_id: uuid.UUID, request: Request, yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    birincil = await _birincil_al(session, ogrenci)
    if birincil is None or birincil.kullanici_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, HESAP_YOK)
    await _hesabi_ayir(session, ogrenci, birincil)
    await audit.kaydet(
        session, "panel_hesabi_ayrildi", kullanici_id=yonetici.id, hedef_tur="ogrenci", hedef_id=str(ogrenci.id),
        ip=_ip(request),
    )
    await session.commit()
    return await _detay(session, ogrenci)


@router.post("/{ogrenci_id}/hesap/sifre-sifirla", response_model=SifreSifirlaYanit)
async def hesap_sifre_sifirla(
    ogrenci_id: uuid.UUID, request: Request, yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    birincil = await _birincil_al(session, ogrenci)
    kullanici = await session.get(Kullanici, birincil.kullanici_id) if birincil and birincil.kullanici_id else None
    if kullanici is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, HESAP_YOK)
    sifre = gecici_sifre_uret()
    kullanici.sifre_ozeti = sifre_ozeti(sifre)
    kullanici.sifre_degistirmeli = True
    kullanici.basarisiz_deneme = 0
    kullanici.kilit_bitis = None
    await _oturumlari_iptal_et(session, kullanici.id)
    await audit.kaydet(
        session, "panel_hesabi_sifre_sifirlandi", kullanici_id=yonetici.id, hedef_tur="ogrenci",
        hedef_id=str(ogrenci.id), ip=_ip(request),
    )
    await session.commit()
    return SifreSifirlaYanit(gecici_sifre=sifre)


@router.post("/{ogrenci_id}/resit-gecisi", response_model=OgrenciDetay)
async def resit_gecisi(
    ogrenci_id: uuid.UUID,
    govde: ResitGecisiGirdi,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _ogrenci_al(session, ogrenci_id)
    if _yas(ogrenci.dogum_tarihi) < 18:
        raise _hata422("Öğrenci 18 yaşından küçük")
    telefon = _telefon_normalize(govde.telefon)
    kisiler = list(
        (await session.execute(select(IletisimKisisi).where(IletisimKisisi.ogrenci_id == ogrenci.id).with_for_update()))
        .scalars()
    )
    eski = next((k for k in kisiler if k.birincil), None)
    if eski is not None and eski.kullanici_id is not None:
        await _hesabi_ayir(session, ogrenci, eski)
    whatsapp_riza = (
        await session.execute(
            select(Riza.id).where(
                Riza.ogrenci_id == ogrenci.id, Riza.tur == RizaTuru.whatsapp, Riza.geri_cekildi.is_(None)
            )
        )
    ).first() is not None

    kendisi = next((k for k in kisiler if k.rol == IletisimRolu.kendisi), None)
    if eski is not None and eski is not kendisi:
        # Tek birincil kısıtı için önce eski birincil kapatılır.
        eski.birincil = False
        eski.whatsapp_izni = False
        await session.flush()
    ad_soyad = govde.ad_soyad or (kendisi.ad_soyad if kendisi else f"{ogrenci.ad} {ogrenci.soyad}")
    if kendisi is None:
        kendisi = IletisimKisisi(ogrenci_id=ogrenci.id, rol=IletisimRolu.kendisi)
        session.add(kendisi)
    kendisi.ad_soyad = ad_soyad
    kendisi.telefon = telefon
    # Öğrencinin kişisel bilgilerindeki telefon ile iletişim telefonu hep aynı kalır.
    ogrenci.telefon = telefon
    kendisi.birincil = True
    kendisi.whatsapp_izni = whatsapp_riza
    await audit.kaydet(
        session, "resit_gecisi", kullanici_id=yonetici.id, hedef_tur="ogrenci", hedef_id=str(ogrenci.id),
        ip=_ip(request),
    )
    await session.commit()
    return await _detay(session, ogrenci)
