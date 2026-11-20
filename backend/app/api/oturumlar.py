import uuid
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, delete, exists, func, or_, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import audit, ders_hakki
from app.config import settings
from app.db import get_session
from app.deps import rol_gerekli
from app.models.kullanici import Kullanici, Rol
from app.api.ogrenciler import _ogrenci_al
from app.models.ogrenci import Ogrenci, OgrenciDurum
from app.models.program import Antrenor, DersOturumu, Grup, OgrenciGrup, OturumDurum, TelafiPlani
from app.models.yoklama import Yoklama, YoklamaDurum
from app.oturumlar import bugun, oturumlari_uret, simdi, yoklama_acilis_zamani, yoklama_kilit_zamani
from app.schemas.oturum import (
    EN_COK_GUN,
    IptalGirdi,
    OturumAntrenor,
    OturumDetay,
    OturumGrup,
    OturumOgrenci,
    OturumOzet,
    TelafiAdayi,
    TelafiPlanGirdi,
    TelafiPlanYanit,
    UretGirdi,
    UretYanit,
    YoklamaGirdi,
)

router = APIRouter(prefix="/api", tags=["oturumlar"])

BULUNAMADI = "Ders oturumu bulunamadı"

Yonetici = Depends(rol_gerekli(Rol.admin))
Yetkili = Depends(rol_gerekli(Rol.admin, Rol.antrenor))


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _etkin_antrenor():
    """Oturumun antrenörü: yerine bakan varsa o, yoksa grubun antrenörü."""
    return func.coalesce(DersOturumu.antrenor_id, Grup.antrenor_id)


def _antrenor_kosulu(antrenor_id: uuid.UUID):
    """Antrenörün oturumları: yerine bakan o ise ya da yerine bakan yok ve grubu onunsa."""
    return or_(
        DersOturumu.antrenor_id == antrenor_id,
        and_(DersOturumu.antrenor_id.is_(None), Grup.antrenor_id == antrenor_id),
    )


async def _kendi_antrenor_kaydi(session: AsyncSession, kullanici: Kullanici) -> Antrenor:
    antrenor = (
        await session.execute(select(Antrenor).where(Antrenor.kullanici_id == kullanici.id))
    ).scalar_one_or_none()
    if antrenor is None or not antrenor.aktif:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yetkiniz yok")
    return antrenor


async def _ozetler(session: AsyncSession, kosullar: list) -> list[OturumOzet]:
    ant = aliased(Antrenor)
    yoklama_var = exists().where(Yoklama.oturum_id == DersOturumu.id)
    satirlar = (
        await session.execute(
            select(DersOturumu, Grup.ad, ant.id, ant.ad_soyad, yoklama_var)
            .join(Grup, Grup.id == DersOturumu.grup_id)
            .outerjoin(ant, ant.id == _etkin_antrenor())
            .where(*kosullar)
            .order_by(DersOturumu.tarih, DersOturumu.baslangic, Grup.ad, DersOturumu.id)
        )
    ).all()
    if not satirlar:
        return []
    idler = [o.id for o, *_ in satirlar]
    # O tarihteki aktif üyelikler ile telafi planı tek sorguda sayılır (aynı öğrenci bir kez).
    uyeler = (
        select(DersOturumu.id.label("oturum_id"), OgrenciGrup.ogrenci_id.label("ogrenci_id"))
        .join(OgrenciGrup, OgrenciGrup.grup_id == DersOturumu.grup_id)
        .where(
            DersOturumu.id.in_(idler),
            OgrenciGrup.baslangic <= DersOturumu.tarih,
            or_(OgrenciGrup.bitis.is_(None), OgrenciGrup.bitis >= DersOturumu.tarih),
        )
    )
    telafi = select(TelafiPlani.oturum_id, TelafiPlani.ogrenci_id).where(TelafiPlani.oturum_id.in_(idler))
    birlesik = union_all(uyeler, telafi).subquery()
    sayilar = dict(
        (
            await session.execute(
                select(birlesik.c.oturum_id, func.count(func.distinct(birlesik.c.ogrenci_id))).group_by(
                    birlesik.c.oturum_id
                )
            )
        ).all()
    )
    return [
        OturumOzet(
            id=o.id,
            tarih=o.tarih,
            baslangic=o.baslangic,
            bitis=o.bitis,
            durum=o.durum,
            grup=OturumGrup(id=o.grup_id, ad=grup_ad),
            antrenor=OturumAntrenor(id=ant_id, ad_soyad=ant_ad) if ant_id is not None else None,
            ogrenci_sayisi=sayilar.get(o.id, 0),
            yoklama_alindi=bool(var),
        )
        for o, grup_ad, ant_id, ant_ad, var in satirlar
    ]


async def _oturum_al(session: AsyncSession, oturum_id: uuid.UUID, kullanici: Kullanici) -> OturumOzet:
    """Oturumu getirir. Antrenör yalnızca kendi oturumunu görebilir."""
    ozetler = await _ozetler(session, [DersOturumu.id == oturum_id])
    if not ozetler:
        raise HTTPException(status.HTTP_404_NOT_FOUND, BULUNAMADI)
    ozet = ozetler[0]
    if kullanici.rol == Rol.antrenor:
        antrenor = await _kendi_antrenor_kaydi(session, kullanici)
        if ozet.antrenor is None or ozet.antrenor.id != antrenor.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yetkiniz yok")
    return ozet


async def _ogrenci_listesi(session: AsyncSession, ozet: OturumOzet) -> list[tuple[Ogrenci, bool]]:
    """Oturumun öğrencileri: o tarihteki aktif üyeler ve telafi planındakiler (telafi_mi = True)."""
    uyeler = (
        await session.execute(
            select(Ogrenci)
            .join(OgrenciGrup, OgrenciGrup.ogrenci_id == Ogrenci.id)
            .where(
                OgrenciGrup.grup_id == ozet.grup.id,
                OgrenciGrup.baslangic <= ozet.tarih,
                or_(OgrenciGrup.bitis.is_(None), OgrenciGrup.bitis >= ozet.tarih),
            )
        )
    ).scalars()
    telafiler = (
        await session.execute(
            select(Ogrenci)
            .join(TelafiPlani, TelafiPlani.ogrenci_id == Ogrenci.id)
            .where(TelafiPlani.oturum_id == ozet.id)
        )
    ).scalars()
    kayit: dict[uuid.UUID, tuple[Ogrenci, bool]] = {o.id: (o, False) for o in uyeler}
    for o in telafiler:
        kayit[o.id] = (o, True)
    return sorted(kayit.values(), key=lambda t: (t[0].soyad, t[0].ad, str(t[0].id)))


async def _detay(session: AsyncSession, ozet: OturumOzet) -> OturumDetay:
    liste = await _ogrenci_listesi(session, ozet)
    idler = [o.id for o, _ in liste]
    yoklamalar: dict[uuid.UUID, Yoklama] = {}
    if idler:
        yoklamalar = {
            y.ogrenci_id: y
            for y in (
                await session.execute(
                    select(Yoklama).where(Yoklama.oturum_id == ozet.id, Yoklama.ogrenci_id.in_(idler))
                )
            ).scalars()
        }
    bakiyeler = await ders_hakki.bakiyeler(session, idler)
    ilk_kayit = (
        await session.execute(select(DersOturumu.yoklama_ilk_kayit).where(DersOturumu.id == ozet.id))
    ).scalar_one()
    kilit = yoklama_kilit_zamani(ilk_kayit)
    return OturumDetay(
        **ozet.model_dump(),
        kilit_zamani=kilit,
        kilitli=kilit is not None and simdi() > kilit,
        ogrenciler=[
            OturumOgrenci(
                ogrenci_id=o.id,
                ad=o.ad,
                soyad=o.soyad,
                foto_var=o.foto_anahtar is not None,
                telafi_mi=telafi_mi,
                yoklama=y.durum if (y := yoklamalar.get(o.id)) else None,
                sebep=y.sebep if y else None,
                aciklama=y.aciklama if y else None,
                bakiye=bakiyeler[o.id],
            )
            for o, telafi_mi in liste
        ],
    )


def _aralik_dogrula(baslangic: date, bitis: date) -> None:
    if bitis < baslangic:
        raise HTTPException(422, "Bitiş tarihi başlangıçtan önce olamaz")
    if (bitis - baslangic).days + 1 > EN_COK_GUN:
        raise HTTPException(422, f"Aralık en çok {EN_COK_GUN} gün olabilir")


@router.post("/oturumlar/uret", response_model=UretYanit)
async def uret(
    govde: UretGirdi,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    sayi = await oturumlari_uret(session, govde.baslangic, govde.bitis)
    await audit.kaydet(
        session, "oturumlar_uretildi", kullanici_id=yonetici.id, hedef_tur="ders_oturumu", ip=_ip(request),
        detay={"olusturulan": sayi},
    )
    await session.commit()
    return UretYanit(olusturulan=sayi)


@router.get("/takvim", response_model=list[OturumOzet])
async def takvim(
    baslangic: date,
    bitis: date,
    antrenor_id: uuid.UUID | None = Query(default=None),
    kullanici: Kullanici = Yetkili,
    session: AsyncSession = Depends(get_session),
):
    _aralik_dogrula(baslangic, bitis)
    kosullar = [DersOturumu.tarih >= baslangic, DersOturumu.tarih <= bitis]
    if kullanici.rol == Rol.antrenor:
        # Antrenör yalnızca kendi oturumlarını görür, antrenor_id parametresi yok sayılır.
        antrenor_id = (await _kendi_antrenor_kaydi(session, kullanici)).id
    if antrenor_id is not None:
        kosullar.append(_antrenor_kosulu(antrenor_id))
    return await _ozetler(session, kosullar)


@router.get("/oturumlar/{oturum_id}", response_model=OturumDetay)
async def getir(oturum_id: uuid.UUID, kullanici: Kullanici = Yetkili, session: AsyncSession = Depends(get_session)):
    ozet = await _oturum_al(session, oturum_id, kullanici)
    return await _detay(session, ozet)


@router.put("/oturumlar/{oturum_id}/yoklama", response_model=OturumDetay)
async def yoklama_al(
    oturum_id: uuid.UUID,
    govde: list[YoklamaGirdi],
    request: Request,
    kullanici: Kullanici = Yetkili,
    session: AsyncSession = Depends(get_session),
):
    ozet = await _oturum_al(session, oturum_id, kullanici)
    if ozet.tarih > bugun():
        raise HTTPException(422, "Gelecek tarihli derse yoklama alınamaz")
    # Antrenör yoklamayı ders başlamadan en erken 15 dakika önce alabilir (yanlış derse girişi önler).
    # Yönetici bu kurala tabi değildir, her zaman düzeltebilir. Saat sunucudan, kulübün saat diliminde.
    if kullanici.rol == Rol.antrenor:
        acilis = yoklama_acilis_zamani(ozet.tarih, ozet.baslangic)
        if simdi() < acilis:
            yerel = acilis.astimezone(ZoneInfo(settings.saat_dilimi))
            raise HTTPException(422, f"Yoklama {yerel:%H:%M}'te açılır (ders başlamadan 15 dakika önce)")
    # Oturum satırı kilitlenir: aynı anda çalışan "dersi iptal et" ile yoklama birbirini atlamasın.
    oturum = (
        await session.execute(select(DersOturumu).where(DersOturumu.id == oturum_id).with_for_update())
    ).scalar_one()
    if oturum.durum == OturumDurum.iptal:
        raise HTTPException(422, "İptal edilmiş derse yoklama alınamaz")
    for g in govde:
        if g.durum == YoklamaDurum.gelmedi and g.sebep is None:
            raise HTTPException(422, "Gelmedi işaretlenen her öğrenci için devamsızlık sebebi seçilmeli")
        if g.durum == YoklamaDurum.geldi and (g.sebep is not None or g.aciklama is not None):
            raise HTTPException(422, "Devamsızlık sebebi ve açıklama yalnız gelmedi için girilebilir")
    idler = [g.ogrenci_id for g in govde]
    if len(idler) != len(set(idler)):
        raise HTTPException(422, "Aynı öğrenci birden fazla kez gönderilmiş")
    liste = {o.id: telafi_mi for o, telafi_mi in await _ogrenci_listesi(session, ozet)}
    if any(i not in liste for i in idler):
        raise HTTPException(422, "Öğrenci bu dersin listesinde değil")
    an = simdi()
    # Satırlar kilitlenir: aynı anda çalışan işçi ya da ikinci istek aynı yoklamayı değiştirmesin.
    mevcut = {}
    if idler:
        mevcut = {
            y.ogrenci_id: y
            for y in (
                await session.execute(
                    select(Yoklama)
                    .where(Yoklama.oturum_id == oturum_id, Yoklama.ogrenci_id.in_(idler))
                    .with_for_update()
                )
            ).scalars()
        }
    # Öğrenci satırları (kimlik sırasıyla) kilitlenir: süre dolumu işi ve telafi planlama ile aynı kilit.
    if idler:
        await session.execute(select(Ogrenci.id).where(Ogrenci.id.in_(idler)).order_by(Ogrenci.id).with_for_update())
    # Kilit: ilk kayıttan 60 dk sonra antrenör değişiklik yapamaz (yeni öğrenci eklemek de değişikliktir).
    # Aynı değerlerin yeniden gönderilmesi değişiklik sayılmaz. Yönetici düzeltebilir, denetim kaydına yazılır.
    degisenler = []
    for g in govde:
        y = mevcut.get(g.ogrenci_id)
        gelmedi = g.durum == YoklamaDurum.gelmedi
        if y is None:
            degisenler.append({"ogrenci_id": str(g.ogrenci_id), "onceki": None, "yeni": g.durum.value})
        elif (y.durum, y.sebep, y.aciklama) != (g.durum, g.sebep if gelmedi else None, g.aciklama if gelmedi else None):
            degisenler.append({"ogrenci_id": str(g.ogrenci_id), "onceki": y.durum.value, "yeni": g.durum.value})
    kilit = yoklama_kilit_zamani(oturum.yoklama_ilk_kayit)
    kilitli = kilit is not None and an > kilit
    if kilitli and degisenler and kullanici.rol == Rol.antrenor:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Yoklama kilitlendi. Düzeltme için yöneticiye başvurun.",
            headers={"X-Hata-Kodu": "yoklama_kilitli"},
        )
    if oturum.yoklama_ilk_kayit is None and govde:
        oturum.yoklama_ilk_kayit = an
    for g in govde:
        y = mevcut.get(g.ogrenci_id)
        if y is None:
            await ders_hakki.yoklama_olustur(
                session,
                oturum_id=oturum_id,
                ogrenci_id=g.ogrenci_id,
                durum=g.durum,
                telafi_mi=liste[g.ogrenci_id],
                isaretleyen_id=kullanici.id,
                simdi=an,
                sebep=g.sebep,
                aciklama=g.aciklama,
            )
        else:
            await ders_hakki.yoklama_uygula(session, y, g.durum, kullanici.id, an, sebep=g.sebep, aciklama=g.aciklama)
    await audit.kaydet(
        session, "yoklama_alindi", kullanici_id=kullanici.id, hedef_tur="ders_oturumu", hedef_id=str(oturum_id),
        ip=_ip(request),
        detay={
            "toplam": len(govde),
            "geldi": sum(1 for g in govde if g.durum.value == "geldi"),
            "gelmedi": sum(1 for g in govde if g.durum.value == "gelmedi"),
        },
    )
    if kilitli and degisenler:
        await audit.kaydet(
            session, "yoklama_kilit_sonrasi_duzeltme", kullanici_id=kullanici.id, hedef_tur="ders_oturumu",
            hedef_id=str(oturum_id), ip=_ip(request), detay={"degisen": degisenler},
        )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Yoklama aynı anda başka biri tarafından değiştirildi, tekrar deneyin")
    ozet = (await _ozetler(session, [DersOturumu.id == oturum_id]))[0]
    return await _detay(session, ozet)


# ---------- ders iptali ----------


async def _oturumu_kilitle(session: AsyncSession, oturum_id: uuid.UUID) -> DersOturumu:
    oturum = (
        await session.execute(select(DersOturumu).where(DersOturumu.id == oturum_id).with_for_update())
    ).scalar_one_or_none()
    if oturum is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, BULUNAMADI)
    return oturum


@router.post("/oturumlar/{oturum_id}/iptal", response_model=OturumDetay)
async def oturum_iptal(
    oturum_id: uuid.UUID,
    request: Request,
    govde: IptalGirdi | None = None,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    """Dersi iptal eder. Yalnız planlı ve yoklaması hiç alınmamış ders iptal edilebilir.
    Derse eklenmiş telafi planları silinir: öğrencilerin telafi hakkı yeniden planlanabilir olur
    (kullanılabilir telafi, iptal edilmemiş ve yoklaması alınmamış planları sayar). Yoklama yazılmadığı için
    ders hakkı defterine dokunulmaz. Oturum üretimi (ON CONFLICT DO NOTHING) iptal edilmiş oturumu yeniden açmaz."""
    oturum = await _oturumu_kilitle(session, oturum_id)
    if oturum.durum == OturumDurum.iptal:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu ders zaten iptal edilmiş")
    if oturum.durum != OturumDurum.planli:
        raise HTTPException(status.HTTP_409_CONFLICT, "Yalnız planlı ders iptal edilebilir")
    yoklama_var = (await session.execute(select(Yoklama.id).where(Yoklama.oturum_id == oturum_id).limit(1))).first()
    if yoklama_var is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Yoklaması alınmış ders iptal edilemez")
    plan_ogrencileri = sorted(
        (await session.execute(
            delete(TelafiPlani).where(TelafiPlani.oturum_id == oturum_id).returning(TelafiPlani.ogrenci_id)
        )).scalars()
    )
    silinen = len(plan_ogrencileri)
    # Geçmiş tarihli bekleyen plan hak ayırıyor olabilir; kalkınca süre dolumu uzlaştırılır.
    for ogrenci_id in plan_ogrencileri:
        await ders_hakki.telafi_uzlastir(session, ogrenci_id, bugun())
    oturum.durum = OturumDurum.iptal
    neden = (govde.neden.strip() if govde and govde.neden else None) or None
    await audit.kaydet(
        session, "oturum_iptal_edildi", kullanici_id=yonetici.id, hedef_tur="ders_oturumu", hedef_id=str(oturum_id),
        ip=_ip(request), detay={"neden": neden, "silinen_telafi": silinen},
    )
    await session.commit()
    ozet = (await _ozetler(session, [DersOturumu.id == oturum_id]))[0]
    return await _detay(session, ozet)


@router.post("/oturumlar/{oturum_id}/geri-al", response_model=OturumDetay)
async def oturum_iptal_geri_al(
    oturum_id: uuid.UUID,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    """İptal edilmiş dersi planlıya döndürür (geçmiş tarihli ders döndürülemez).
    Silinen telafi planları geri gelmez; gerekirse yeniden planlanır."""
    oturum = await _oturumu_kilitle(session, oturum_id)
    if oturum.durum != OturumDurum.iptal:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu ders iptal edilmiş değil")
    if oturum.tarih < bugun():
        raise HTTPException(422, "Geçmiş tarihli ders yeniden açılamaz")
    oturum.durum = OturumDurum.planli
    await audit.kaydet(
        session, "oturum_iptali_geri_alindi", kullanici_id=yonetici.id, hedef_tur="ders_oturumu",
        hedef_id=str(oturum_id), ip=_ip(request),
    )
    await session.commit()
    ozet = (await _ozetler(session, [DersOturumu.id == oturum_id]))[0]
    return await _detay(session, ozet)


# ---------- telafi ----------

EN_COK_TELAFI_GUN = 31


@router.get("/ogrenciler/{ogrenci_id}/telafi-adaylari", response_model=list[TelafiAdayi])
async def telafi_adaylari(
    ogrenci_id: uuid.UUID,
    baslangic: date | None = Query(default=None),
    bitis: date | None = Query(default=None),
    _: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    await _ogrenci_al(session, ogrenci_id)
    bas = baslangic or bugun()
    bit = bitis or (bas + timedelta(days=14))
    if bit < bas:
        raise HTTPException(422, "Bitiş tarihi başlangıçtan önce olamaz")
    if (bit - bas).days + 1 > EN_COK_TELAFI_GUN:
        raise HTTPException(422, f"Aralık en çok {EN_COK_TELAFI_GUN} gün olabilir")
    uye_mi = exists().where(
        OgrenciGrup.ogrenci_id == ogrenci_id,
        OgrenciGrup.grup_id == DersOturumu.grup_id,
        OgrenciGrup.baslangic <= DersOturumu.tarih,
        or_(OgrenciGrup.bitis.is_(None), OgrenciGrup.bitis >= DersOturumu.tarih),
    )
    planli_mi = exists().where(TelafiPlani.oturum_id == DersOturumu.id, TelafiPlani.ogrenci_id == ogrenci_id)
    ozetler = await _ozetler(
        session,
        [
            DersOturumu.tarih >= max(bas, bugun()),
            DersOturumu.tarih <= bit,
            DersOturumu.durum != OturumDurum.iptal,
            Grup.aktif.is_(True),
            ~uye_mi,
            ~planli_mi,
        ],
    )
    if not ozetler:
        return []
    # Kullanılabilir hakkı varsa, son kullanması yetmeyen (hakkın ayından sonraki) tarihler listelenmez.
    # Hiç hakkı yoksa liste eskisi gibi döner; planlama zaten "Kullanılabilir telafi hakkı yok" der.
    if await ders_hakki.kullanilabilir_telafi(session, ogrenci_id) > 0:
        uygun_gun = {
            t: await ders_hakki.kullanilabilir_telafi(session, ogrenci_id, t) > 0 for t in {o.tarih for o in ozetler}
        }
        ozetler = [o for o in ozetler if uygun_gun[o.tarih]]
    kontenjan = dict(
        (await session.execute(select(Grup.id, Grup.kontenjan).where(Grup.id.in_({o.grup.id for o in ozetler})))).all()
    )
    return [
        TelafiAdayi(oturum=o, bos_yer=kontenjan[o.grup.id] - o.ogrenci_sayisi)
        for o in ozetler
        if kontenjan[o.grup.id] - o.ogrenci_sayisi > 0
    ]


@router.get("/ogrenciler/{ogrenci_id}/telafi-planlari", response_model=list[TelafiPlanYanit])
async def telafi_planlari(
    ogrenci_id: uuid.UUID, _: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)
):
    await _ogrenci_al(session, ogrenci_id)
    satirlar = (
        await session.execute(
            select(DersOturumu, Grup.ad, Yoklama.durum)
            .join(TelafiPlani, TelafiPlani.oturum_id == DersOturumu.id)
            .join(Grup, Grup.id == DersOturumu.grup_id)
            .outerjoin(Yoklama, and_(Yoklama.oturum_id == DersOturumu.id, Yoklama.ogrenci_id == ogrenci_id))
            .where(TelafiPlani.ogrenci_id == ogrenci_id)
            .order_by(DersOturumu.tarih.desc(), DersOturumu.baslangic.desc(), DersOturumu.id)
        )
    ).all()
    return [
        TelafiPlanYanit(
            oturum_id=o.id, tarih=o.tarih, baslangic=o.baslangic, bitis=o.bitis,
            grup=OturumGrup(id=o.grup_id, ad=ad), yoklama=durum,
        )
        for o, ad, durum in satirlar
    ]


@router.post("/oturumlar/{oturum_id}/telafi", response_model=OturumDetay)
async def telafi_planla(
    oturum_id: uuid.UUID,
    govde: TelafiPlanGirdi,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    # Önce öğrenci satırı kilitlenir: aynı öğrenci için eşzamanlı planlamalar sırayla işlenir ve
    # son hak iki kez kullanılamaz. Sonra grup satırı kilitlenir: kontenjan yarışı olmaz.
    ogrenci = (
        await session.execute(
            select(Ogrenci).where(Ogrenci.id == govde.ogrenci_id, Ogrenci.sentetik.is_(False)).with_for_update()
        )
    ).scalar_one_or_none()
    if ogrenci is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Öğrenci bulunamadı")
    ozet = await _oturum_al(session, oturum_id, yonetici)
    grup = (await session.execute(select(Grup).where(Grup.id == ozet.grup.id).with_for_update())).scalar_one()
    # Kilit alındıktan sonra güncel sayılar için özet yeniden okunur.
    ozet = await _oturum_al(session, oturum_id, yonetici)
    if ogrenci.durum != OgrenciDurum.aktif:
        raise HTTPException(422, "Pasif öğrenci için telafi planlanamaz")
    if ozet.tarih < bugun():
        raise HTTPException(422, "Geçmiş derse telafi planlanamaz")
    if ozet.durum == OturumDurum.iptal:
        raise HTTPException(422, "İptal edilmiş derse telafi planlanamaz")
    liste = {o.id: telafi_mi for o, telafi_mi in await _ogrenci_listesi(session, ozet)}
    if liste.get(ogrenci.id) is False:
        raise HTTPException(422, "Öğrenci bu grubun üyesi, telafi gerekmez")
    if liste.get(ogrenci.id) is True:
        raise HTTPException(status.HTTP_409_CONFLICT, "Öğrenci bu derse zaten telafi için eklendi")
    if await ders_hakki.kullanilabilir_telafi(session, ogrenci.id) <= 0:
        raise HTTPException(422, "Kullanılabilir telafi hakkı yok")
    if await ders_hakki.kullanilabilir_telafi(session, ogrenci.id, ozet.tarih) <= 0:
        raise HTTPException(
            422,
            "Telafi hakkı bu tarihe kadar geçerli değil: telafi, devamsızlığın olduğu ayın sonuna kadar kullanılabilir",
        )
    if ozet.ogrenci_sayisi >= grup.kontenjan:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu derste boş yer yok")
    session.add(TelafiPlani(oturum_id=oturum_id, ogrenci_id=ogrenci.id, olusturan_id=yonetici.id))
    await audit.kaydet(
        session, "telafi_planlandi", kullanici_id=yonetici.id, hedef_tur="ders_oturumu", hedef_id=str(oturum_id),
        ip=_ip(request), detay={"ogrenci_id": str(ogrenci.id)},
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Öğrenci bu derse zaten telafi için eklendi")
    ozet = (await _ozetler(session, [DersOturumu.id == oturum_id]))[0]
    return await _detay(session, ozet)


@router.delete("/oturumlar/{oturum_id}/telafi/{ogrenci_id}", response_model=OturumDetay)
async def telafi_iptal(
    oturum_id: uuid.UUID,
    ogrenci_id: uuid.UUID,
    request: Request,
    yonetici: Kullanici = Yonetici,
    session: AsyncSession = Depends(get_session),
):
    await _oturum_al(session, oturum_id, yonetici)
    plan = (
        await session.execute(
            select(TelafiPlani)
            .where(TelafiPlani.oturum_id == oturum_id, TelafiPlani.ogrenci_id == ogrenci_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Telafi planı bulunamadı")
    yoklama_var = (
        await session.execute(
            select(Yoklama.id).where(Yoklama.oturum_id == oturum_id, Yoklama.ogrenci_id == ogrenci_id)
        )
    ).first()
    if yoklama_var is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Yoklaması alınmış telafi geri alınamaz")
    await session.delete(plan)
    await session.flush()
    # Geçmiş tarihli bekleyen plan hak ayırıyordu; kalkınca süre dolumu uzlaştırılır.
    await ders_hakki.telafi_uzlastir(session, ogrenci_id, bugun())
    await audit.kaydet(
        session, "telafi_iptal_edildi", kullanici_id=yonetici.id, hedef_tur="ders_oturumu", hedef_id=str(oturum_id),
        ip=_ip(request), detay={"ogrenci_id": str(ogrenci_id)},
    )
    await session.commit()
    ozet = (await _ozetler(session, [DersOturumu.id == oturum_id]))[0]
    return await _detay(session, ozet)
