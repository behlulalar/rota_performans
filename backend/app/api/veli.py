"""Veli ve reşit öğrenci paneli. Kullanıcı yalnızca kendi hesabına bağlı öğrencileri görür."""
import asyncio
import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import audit, ders_hakki
from app import telefon as telefon_modulu
from app.db import get_session
from app.depolama import depolama
from app.deps import rol_gerekli
from app.config import settings
from app.models.bildirim import BildirimTercihi, PushAbonelik
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import IletisimKisisi, Ogrenci
from app.models.paket import Odeme, OgrenciPaketi, OgrenciPaketiDurum, Paket
from app.models.program import DersOturumu, Grup, GrupProgrami, OgrenciGrup, OturumDurum, TelafiPlani
from app.models.yoklama import DersHakkiHareketi, HareketTuru, Sayac, Yoklama
from app.oturumlar import bugun
from app.schemas.veli import (
    BildirimTercihleri,
    BildirimTercihYaniti,
    CocukDetay,
    CocukOzet,
    DersOzeti,
    Profil,
    PushAbonelikGiris,
    PushAbonelikSil,
    PushAnahtari,
    ProfilGuncelle,
    VeliDers,
    VeliGrup,
    VeliHareket,
    VeliOdeme,
    VeliPaket,
    VeliProgramSatiri,
)

router = APIRouter(prefix="/api/benim", tags=["veli"])

Veli = Depends(rol_gerekli(Rol.veli, Rol.ogrenci))

YAKLASAN_GUN = 28
GECMIS_DERS_SAYISI = 20
HAREKET_SAYISI = 50
BULUNAMADI = "Öğrenci bulunamadı"


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _benim_kosulu(kullanici: Kullanici):
    """Hesabın erişebildiği öğrenciler: veli için iletişim kişisi bağı, reşit öğrenci için kendi hesabı."""
    if kullanici.rol == Rol.ogrenci:
        return Ogrenci.kullanici_id == kullanici.id
    return Ogrenci.id.in_(select(IletisimKisisi.ogrenci_id).where(IletisimKisisi.kullanici_id == kullanici.id))


async def _cocuklar(session: AsyncSession, kullanici: Kullanici) -> list[Ogrenci]:
    return list(
        (
            await session.execute(
                select(Ogrenci)
                .where(_benim_kosulu(kullanici), Ogrenci.sentetik.is_(False))
                .order_by(Ogrenci.ad, Ogrenci.soyad, Ogrenci.id)
            )
        ).scalars()
    )


async def _cocuk_al(session: AsyncSession, kullanici: Kullanici, ogrenci_id: uuid.UUID) -> Ogrenci:
    # Başkasının öğrencisi için de 404 döner: kayıt var mı yok mu belli edilmez.
    ogrenci = (
        await session.execute(
            select(Ogrenci).where(Ogrenci.id == ogrenci_id, _benim_kosulu(kullanici), Ogrenci.sentetik.is_(False))
        )
    ).scalar_one_or_none()
    if ogrenci is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, BULUNAMADI)
    return ogrenci


async def _dersler(
    session: AsyncSession, ogrenci_id: uuid.UUID, kosullar: list, *, ters: bool = False, limit: int | None = None
) -> list[VeliDers]:
    """Öğrencinin kendi grubundaki dersleri ile telafi için eklendiği dersler (tarihe göre)."""
    uye_mi = (
        select(OgrenciGrup.id)
        .where(
            OgrenciGrup.ogrenci_id == ogrenci_id,
            OgrenciGrup.grup_id == DersOturumu.grup_id,
            OgrenciGrup.baslangic <= DersOturumu.tarih,
            or_(OgrenciGrup.bitis.is_(None), OgrenciGrup.bitis >= DersOturumu.tarih),
        )
        .exists()
    )
    telafi_mi = (
        select(TelafiPlani.id)
        .where(TelafiPlani.oturum_id == DersOturumu.id, TelafiPlani.ogrenci_id == ogrenci_id)
        .exists()
    )
    yoklama = aliased(Yoklama)
    sira = (DersOturumu.tarih.desc(), DersOturumu.baslangic.desc()) if ters else (DersOturumu.tarih, DersOturumu.baslangic)
    sorgu = (
        select(DersOturumu, Grup.ad, telafi_mi, yoklama.durum, yoklama.sebep)
        .join(Grup, Grup.id == DersOturumu.grup_id)
        .outerjoin(yoklama, (yoklama.oturum_id == DersOturumu.id) & (yoklama.ogrenci_id == ogrenci_id))
        .where(or_(uye_mi, telafi_mi), *kosullar)
        .order_by(*sira, DersOturumu.id)
    )
    if limit is not None:
        sorgu = sorgu.limit(limit)
    return [
        VeliDers(
            oturum_id=o.id, tarih=o.tarih, baslangic=o.baslangic, bitis=o.bitis, grup_ad=grup_ad,
            telafi_mi=bool(telafi), durum=o.durum, yoklama=durum, sebep=sebep,
        )
        for o, grup_ad, telafi, durum, sebep in (await session.execute(sorgu)).all()
    ]


async def _ozetler(session: AsyncSession, cocuklar: list[Ogrenci]) -> list[CocukOzet]:
    if not cocuklar:
        return []
    idler = [c.id for c in cocuklar]
    gruplar: dict[uuid.UUID, list[VeliGrup]] = {i: [] for i in idler}
    for ogrenci_id, grup_id, ad in (
        await session.execute(
            select(OgrenciGrup.ogrenci_id, Grup.id, Grup.ad)
            .join(Grup, Grup.id == OgrenciGrup.grup_id)
            .where(OgrenciGrup.ogrenci_id.in_(idler), OgrenciGrup.bitis.is_(None))
            .order_by(Grup.ad, Grup.id)
        )
    ).all():
        gruplar[ogrenci_id].append(VeliGrup(id=grup_id, ad=ad))
    bekleyen = dict(
        (
            await session.execute(
                select(OgrenciPaketi.ogrenci_id, func.count())
                .where(
                    OgrenciPaketi.ogrenci_id.in_(idler), OgrenciPaketi.durum == OgrenciPaketiDurum.odeme_bekliyor
                )
                .group_by(OgrenciPaketi.ogrenci_id)
            )
        ).all()
    )
    odenmis = {
        i
        for (i,) in (
            await session.execute(
                select(OgrenciPaketi.ogrenci_id)
                .where(OgrenciPaketi.ogrenci_id.in_(idler), OgrenciPaketi.durum == OgrenciPaketiDurum.odendi)
                .distinct()
            )
        ).all()
    }
    bakiyeler = await ders_hakki.bakiyeler(session, idler)
    sonuc = []
    for c in cocuklar:
        siradaki = await _dersler(
            session, c.id, [DersOturumu.tarih >= bugun(), DersOturumu.durum != OturumDurum.iptal], limit=1
        )
        sonuc.append(
            CocukOzet(
                id=c.id, ad=c.ad, soyad=c.soyad, foto_var=c.foto_anahtar is not None, durum=c.durum,
                gruplar=gruplar[c.id],
                ders_hakki={**bakiyeler[c.id], "kullanilabilir_telafi": await ders_hakki.kullanilabilir_telafi(session, c.id)},
                siradaki_ders=siradaki[0] if siradaki else None,
                odeme_bekleyen=bekleyen.get(c.id, 0),
                ders_hakki_bitti=c.id in odenmis and bakiyeler[c.id]["normal"] <= 0,
            )
        )
    return sonuc


@router.get("/cocuklar", response_model=list[CocukOzet])
async def cocuklar(kullanici: Kullanici = Veli, session: AsyncSession = Depends(get_session)):
    return await _ozetler(session, await _cocuklar(session, kullanici))


@router.get("/cocuklar/{ogrenci_id}", response_model=CocukDetay)
async def cocuk_detay(ogrenci_id: uuid.UUID, kullanici: Kullanici = Veli, session: AsyncSession = Depends(get_session)):
    ogrenci = await _cocuk_al(session, kullanici, ogrenci_id)
    ozet = (await _ozetler(session, [ogrenci]))[0]
    bugun_ = bugun()
    program = [
        VeliProgramSatiri(grup_ad=ad, gun=p.gun, baslangic=p.baslangic, bitis=p.bitis)
        for p, ad in (
            await session.execute(
                select(GrupProgrami, Grup.ad)
                .join(Grup, Grup.id == GrupProgrami.grup_id)
                .join(OgrenciGrup, OgrenciGrup.grup_id == Grup.id)
                .where(OgrenciGrup.ogrenci_id == ogrenci.id, OgrenciGrup.bitis.is_(None), Grup.aktif.is_(True))
                .order_by(GrupProgrami.gun, GrupProgrami.baslangic, Grup.ad)
            )
        ).all()
    ]
    yaklasan = await _dersler(
        session, ogrenci.id,
        [
            DersOturumu.tarih >= bugun_,
            DersOturumu.tarih <= bugun_ + timedelta(days=YAKLASAN_GUN),
            DersOturumu.durum != OturumDurum.iptal,
        ],
    )
    gecmis = await _dersler(
        session, ogrenci.id, [DersOturumu.tarih < bugun_, DersOturumu.durum != OturumDurum.iptal],
        ters=True, limit=GECMIS_DERS_SAYISI,
    )
    return CocukDetay(
        **ozet.model_dump(),
        program=program,
        yaklasan_dersler=yaklasan,
        gecmis_dersler=gecmis,
        paketler=await _paketler(session, ogrenci.id),
        ders_ozeti=await _ders_ozeti(session, ozet),
        hareketler=await _hareketler(session, ogrenci.id),
    )


async def _paketler(session: AsyncSession, ogrenci_id: uuid.UUID) -> list[VeliPaket]:
    satirlar = (
        await session.execute(
            select(OgrenciPaketi, Paket.ad)
            .join(Paket, Paket.id == OgrenciPaketi.paket_id)
            .where(OgrenciPaketi.ogrenci_id == ogrenci_id, OgrenciPaketi.durum != OgrenciPaketiDurum.iptal)
            .order_by(OgrenciPaketi.olusturma.desc(), OgrenciPaketi.id)
        )
    ).all()
    odemeler: dict[uuid.UUID, list[Odeme]] = {}
    if satirlar:
        for o in (
            await session.execute(
                select(Odeme)
                .where(Odeme.ogrenci_paketi_id.in_([op.id for op, _ in satirlar]))
                .order_by(Odeme.tarih.desc(), Odeme.olusturma.desc(), Odeme.id)
            )
        ).scalars():
            odemeler.setdefault(o.ogrenci_paketi_id, []).append(o)
    sonuc = []
    for op, ad in satirlar:
        liste = odemeler.get(op.id, [])
        sonuc.append(
            VeliPaket(
                id=op.id, paket_adi=ad, ders_sayisi=op.ders_sayisi, uygulanan_fiyat=op.uygulanan_fiyat,
                toplam_odenen=sum((o.tutar for o in liste if o.iptal_zamani is None), start=0),
                durum=op.durum, baslangic=op.baslangic, bitis=op.bitis, olusturma=op.olusturma,
                odemeler=[
                    VeliOdeme(tarih=o.tarih, tutar=o.tutar, yontem=o.yontem, iptal=o.iptal_zamani is not None)
                    for o in liste
                ],
            )
        )
    return sonuc


async def _ders_ozeti(session: AsyncSession, ozet: CocukOzet) -> DersOzeti:
    # Geri alınan kayıtlar ve onları geri alan ters kayıtlar birlikte sayım dışı kalır.
    geri_alinan = select(DersHakkiHareketi.iptal_edilen_id).where(DersHakkiHareketi.iptal_edilen_id.is_not(None))
    toplamlar: dict[tuple[Sayac, HareketTuru], int] = {
        (sayac, tur): int(miktar)
        for sayac, tur, miktar in (
            await session.execute(
                select(DersHakkiHareketi.sayac, DersHakkiHareketi.tur, func.sum(DersHakkiHareketi.miktar))
                .where(
                    DersHakkiHareketi.ogrenci_id == ozet.id,
                    DersHakkiHareketi.tur != HareketTuru.iptal,
                    DersHakkiHareketi.id.not_in(geri_alinan),
                )
                .group_by(DersHakkiHareketi.sayac, DersHakkiHareketi.tur)
            )
        ).all()
    }
    normal = lambda t: toplamlar.get((Sayac.normal, t), 0)  # noqa: E731
    telafi = lambda t: toplamlar.get((Sayac.telafi, t), 0)  # noqa: E731
    return DersOzeti(
        toplam=normal(HareketTuru.paket_yuklemesi) + normal(HareketTuru.manuel_duzeltme),
        katildi=-normal(HareketTuru.ders_kullanimi),
        devamsiz=-normal(HareketTuru.devamsizlik),
        kalan=ozet.ders_hakki.normal,
        telafi_dogan=telafi(HareketTuru.devamsizlik) + telafi(HareketTuru.manuel_duzeltme),
        telafi_kullanilan=-telafi(HareketTuru.telafi_kullanimi),
        telafi_yanan=-telafi(HareketTuru.telafi_suresi_doldu),
        telafi_kalan=ozet.ders_hakki.telafi,
    )


async def _hareketler(session: AsyncSession, ogrenci_id: uuid.UUID) -> list[VeliHareket]:
    # Yönetici notları (neden) ve kullanıcı bilgisi veliye gösterilmez.
    return [
        VeliHareket(zaman=h.zaman, sayac=h.sayac, miktar=h.miktar, tur=h.tur, son_kullanma=h.son_kullanma)
        for h in (
            await session.execute(
                select(DersHakkiHareketi)
                .where(DersHakkiHareketi.ogrenci_id == ogrenci_id)
                .order_by(DersHakkiHareketi.zaman.desc(), DersHakkiHareketi.id.desc())
                .limit(HAREKET_SAYISI)
            )
        ).scalars()
    ]


FotoBoyut = Literal["kucuk", "buyuk"]


@router.get("/cocuklar/{ogrenci_id}/foto")
async def cocuk_foto(
    ogrenci_id: uuid.UUID,
    request: Request,
    boyut: FotoBoyut = "kucuk",
    kullanici: Kullanici = Veli,
    session: AsyncSession = Depends(get_session),
):
    ogrenci = await _cocuk_al(session, kullanici, ogrenci_id)
    veri = await asyncio.to_thread(depolama.oku, ogrenci.foto_anahtar, boyut) if ogrenci.foto_anahtar else None
    if veri is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fotoğraf bulunamadı")
    basliklar = {"Cache-Control": "private, max-age=86400", "ETag": f'"{ogrenci.foto_anahtar}-{boyut}"'}
    if request.headers.get("if-none-match") == basliklar["ETag"]:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=basliklar)
    return Response(content=veri, media_type="image/jpeg", headers=basliklar)


# ---------- profil ----------


async def _kendi_kisileri(session: AsyncSession, kullanici: Kullanici) -> list[IletisimKisisi]:
    return list(
        (
            await session.execute(
                select(IletisimKisisi)
                .where(IletisimKisisi.kullanici_id == kullanici.id)
                .order_by(IletisimKisisi.birincil.desc(), IletisimKisisi.olusturma, IletisimKisisi.id)
            )
        ).scalars()
    )


@router.get("/profil", response_model=Profil)
async def profil(kullanici: Kullanici = Veli, session: AsyncSession = Depends(get_session)):
    kisiler = await _kendi_kisileri(session, kullanici)
    ilk = kisiler[0] if kisiler else None
    return Profil(
        giris=kullanici.giris, rol=kullanici.rol,
        ad_soyad=(ilk.ad_soyad if ilk else None) or kullanici.ad_soyad,
        telefon=ilk.telefon if ilk else None,
    )


@router.patch("/profil", response_model=Profil)
async def profil_guncelle(
    govde: ProfilGuncelle,
    request: Request,
    kullanici: Kullanici = Veli,
    session: AsyncSession = Depends(get_session),
):
    try:
        telefon = telefon_modulu.normalize(govde.telefon)
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    kisiler = await _kendi_kisileri(session, kullanici)
    if not kisiler:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profil bulunamadı")
    # Kardeşlerde aynı hesap birden çok satıra bağlıdır; hepsi birlikte güncellenir.
    for k in kisiler:
        k.ad_soyad = govde.ad_soyad
        k.telefon = telefon
    kullanici.ad_soyad = govde.ad_soyad
    if kullanici.rol == Rol.ogrenci:
        # Reşit öğrencinin telefonu öğrenci kaydında da tutulur.
        for ogrenci in (
            await session.execute(select(Ogrenci).where(Ogrenci.kullanici_id == kullanici.id))
        ).scalars():
            ogrenci.telefon = telefon
    # Giriş bilgisi (telefon/e-posta) buradan değişmez: hesap ele geçirilirse kilit dışı kalınmasın.
    await audit.kaydet(
        session, "profil_guncellendi", kullanici_id=kullanici.id, hedef_tur="kullanici",
        hedef_id=str(kullanici.id), ip=_ip(request),
    )
    await session.commit()
    return Profil(giris=kullanici.giris, rol=kullanici.rol, ad_soyad=govde.ad_soyad, telefon=telefon)


# ---------- bildirim tercihleri ----------


async def _tercih_yaniti(session: AsyncSession, kullanici: Kullanici, t: BildirimTercihi | None) -> BildirimTercihYaniti:
    izin = (
        await session.execute(
            select(IletisimKisisi.id)
            .where(IletisimKisisi.kullanici_id == kullanici.id, IletisimKisisi.whatsapp_izni.is_(True))
            .limit(1)
        )
    ).first()
    # Kayıt yoksa varsayılanlar (hepsi açık) döner.
    return BildirimTercihYaniti(
        ders_gelmedi=t.ders_gelmedi if t else True,
        ders_hakki=t.ders_hakki if t else True,
        whatsapp=t.whatsapp if t else True,
        push=t.push if t else True,
        whatsapp_izni_var=izin is not None,
    )


@router.get("/bildirim-tercihleri", response_model=BildirimTercihYaniti)
async def bildirim_tercihleri(kullanici: Kullanici = Veli, session: AsyncSession = Depends(get_session)):
    return await _tercih_yaniti(session, kullanici, await session.get(BildirimTercihi, kullanici.id))


@router.put("/bildirim-tercihleri", response_model=BildirimTercihYaniti)
async def bildirim_tercihleri_kaydet(
    govde: BildirimTercihleri,
    request: Request,
    kullanici: Kullanici = Veli,
    session: AsyncSession = Depends(get_session),
):
    t = await session.get(BildirimTercihi, kullanici.id)
    if t is None:
        t = BildirimTercihi(kullanici_id=kullanici.id)
        session.add(t)
    for alan, deger in govde.model_dump().items():
        setattr(t, alan, deger)
    t.guncelleme = func.now()
    await audit.kaydet(
        session, "bildirim_tercihi_guncellendi", kullanici_id=kullanici.id, hedef_tur="kullanici",
        hedef_id=str(kullanici.id), ip=_ip(request), detay=govde.model_dump(),
    )
    await session.commit()
    await session.refresh(t)
    return await _tercih_yaniti(session, kullanici, t)


# ---------- web push cihaz kaydı ----------


@router.get("/push/anahtar", response_model=PushAnahtari)
async def push_anahtari(kullanici: Kullanici = Veli):
    if not settings.push_etkin:
        return PushAnahtari(etkin=False)
    return PushAnahtari(etkin=True, anahtar=settings.vapid_public_key)


@router.post("/push/abonelik", status_code=status.HTTP_204_NO_CONTENT)
async def push_abonelik_kaydet(
    govde: PushAbonelikGiris,
    request: Request,
    kullanici: Kullanici = Veli,
    session: AsyncSession = Depends(get_session),
):
    """Aynı uç nokta başka hesapta kayıtlıysa (ortak cihaz) bu hesaba taşınır."""
    a = (await session.execute(select(PushAbonelik).where(PushAbonelik.endpoint == govde.endpoint))).scalar_one_or_none()
    if a is None:
        a = PushAbonelik(endpoint=govde.endpoint)
        session.add(a)
    a.kullanici_id = kullanici.id
    a.p256dh = govde.keys.p256dh
    a.auth = govde.keys.auth
    a.cihaz = govde.cihaz
    await audit.kaydet(
        session, "push_abonelik_kaydedildi", kullanici_id=kullanici.id, hedef_tur="kullanici",
        hedef_id=str(kullanici.id), ip=_ip(request),
    )
    await session.commit()


@router.delete("/push/abonelik", status_code=status.HTTP_204_NO_CONTENT)
async def push_abonelik_sil(
    govde: PushAbonelikSil,
    request: Request,
    kullanici: Kullanici = Veli,
    session: AsyncSession = Depends(get_session),
):
    """Yalnız kendi aboneliğini siler; olmayan kayıt için de 204 döner."""
    a = (
        await session.execute(
            select(PushAbonelik).where(PushAbonelik.endpoint == govde.endpoint, PushAbonelik.kullanici_id == kullanici.id)
        )
    ).scalar_one_or_none()
    if a is not None:
        await session.delete(a)
        await audit.kaydet(
            session, "push_abonelik_silindi", kullanici_id=kullanici.id, hedef_tur="kullanici",
            hedef_id=str(kullanici.id), ip=_ip(request),
        )
        await session.commit()
