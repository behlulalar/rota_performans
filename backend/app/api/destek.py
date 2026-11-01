"""Teknik destek uçları (yalnız destek rolü): sistem durumu, tüm roller için hesap yönetimi,
bildirim kuyruğunun teknik görünümü. Her yazma işlemi denetim kaydına düşer; denetim kaydı ekranı
(`/api/denetim`) de yalnız destek içindir."""
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from redis.asyncio import Redis
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.api.antrenorler import _oturumlari_iptal_et, gecici_sifre_uret
from app.api.bildirim_yonetimi import yeniden_denemeye_al
from app.api.yoneticiler import KENDINI_PASIFE_ALMA, SON_YONETICI
from app.bildirim import metin_olustur
from app.config import settings
from app.db import get_session
from app.deps import rol_gerekli
from app.isci import KALP_ATISI_ANAHTAR
from app.models.bildirim import Bildirim, BildirimDurum, BildirimKanal
from app.models.kullanici import Kullanici, Oturum, Rol
from app.ratelimit import get_redis
from app.schemas.antrenor import SifreSifirlaYanit
from app.schemas.destek import (
    DestekBildirimListesi,
    DestekBildirimSatiri,
    HesapListesi,
    HesapSatiri,
    IsciDurumu,
    KuyrukSayilari,
    OturumKapatYaniti,
    OturumSatiri,
    Ping,
    SistemDurumu,
    TopluIslemIstegi,
    TopluIslemYaniti,
)
from app.security import sifre_ozeti, simdi

router = APIRouter(prefix="/api/destek", tags=["destek"])

Destek = Depends(rol_gerekli(Rol.destek))

BULUNAMADI = "Hesap bulunamadı"
KENDI_SIFRESI = "Kendi şifrenizi Ayarlar > Hesabım bölümünden değiştirin"
# İşçi 30 sn'de bir atış yazar; bundan eskisi "canlı değil" sayılır.
ISCI_CANLI_SANIYE = 90


def _ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


# --- Sistem durumu ---


@router.get("/sistem-durumu", response_model=SistemDurumu)
async def sistem_durumu(
    _: Kullanici = Destek,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    async def olc(sorgu) -> Ping:
        t0 = time.perf_counter()
        try:
            await sorgu()
        except Exception:
            return Ping(ok=False)
        return Ping(ok=True, gecikme_ms=round((time.perf_counter() - t0) * 1000, 2))

    veritabani = await olc(lambda: session.execute(text("SELECT 1")))
    redis_ping = await olc(redis.ping)

    isci = IsciDurumu(canli=False)
    if redis_ping.ok:
        ham = await redis.get(KALP_ATISI_ANAHTAR)
        if ham and ham.isdigit():
            fark = max(0, int(time.time()) - int(ham))
            isci = IsciDurumu(
                canli=fark <= ISCI_CANLI_SANIYE,
                son_atis=datetime.fromtimestamp(int(ham), tz=timezone.utc),
                saniye_once=fark,
            )

    kuyruk = KuyrukSayilari()
    if veritabani.ok:
        sayilar = {d.value: n for d, n in (await session.execute(select(Bildirim.durum, func.count()).group_by(Bildirim.durum))).all()}
        geciken = (
            await session.execute(
                select(func.count()).where(
                    Bildirim.durum == BildirimDurum.bekliyor, Bildirim.planli_zaman < datetime.now(timezone.utc)
                )
            )
        ).scalar_one()
        kuyruk = KuyrukSayilari(**sayilar, geciken_bekleyen=geciken)

    return SistemDurumu(
        ortam=settings.env,
        surum=settings.surum,
        veritabani=veritabani,
        redis=redis_ping,
        isci=isci,
        bildirim_kuyrugu=kuyruk,
        push_yapilandirildi=settings.push_etkin,
        whatsapp_yapilandirildi=settings.whatsapp_etkin,
    )


# --- Hesap yönetimi ---


def _satir(k: Kullanici, ben_id: uuid.UUID) -> HesapSatiri:
    return HesapSatiri(
        id=k.id, giris=k.giris, ad_soyad=k.ad_soyad, rol=k.rol, aktif=k.aktif,
        kilitli=k.kilit_bitis is not None and k.kilit_bitis > simdi(), kilit_bitis=k.kilit_bitis,
        son_giris=k.son_giris, olusturma=k.olusturma, sifre_degistirmeli=k.sifre_degistirmeli,
        totp_aktif=k.totp_aktif, ben=k.id == ben_id,
    )


async def _hesap_al(session: AsyncSession, hesap_id: uuid.UUID) -> Kullanici:
    k = (await session.execute(select(Kullanici).where(Kullanici.id == hesap_id).with_for_update())).scalar_one_or_none()
    if k is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, BULUNAMADI)
    return k


@router.get("/hesaplar", response_model=HesapListesi)
async def hesaplari_listele(
    q: str | None = Query(default=None, max_length=100),
    rol: Rol | None = Query(default=None),
    sayfa: int = Query(default=1, ge=1),
    boyut: int = Query(default=20, ge=1, le=100),
    ben: Kullanici = Destek,
    session: AsyncSession = Depends(get_session),
):
    kosullar = []
    if rol is not None:
        kosullar.append(Kullanici.rol == rol)
    if q and q.strip():
        kacis = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        desen = f"%{kacis}%"
        kosullar.append(
            or_(
                Kullanici.giris.ilike(desen, escape="\\"),
                Kullanici.ad_soyad.ilike(desen, escape="\\"),
                Kullanici.telefon.ilike(desen, escape="\\"),
            )
        )
    toplam = (await session.execute(select(func.count()).select_from(Kullanici).where(*kosullar))).scalar_one()
    satirlar = (
        await session.execute(
            select(Kullanici)
            .where(*kosullar)
            .order_by(Kullanici.olusturma.desc(), Kullanici.id)
            .limit(boyut)
            .offset((sayfa - 1) * boyut)
        )
    ).scalars()
    return HesapListesi(kayitlar=[_satir(k, ben.id) for k in satirlar], toplam=toplam, sayfa=sayfa, boyut=boyut)


@router.post("/hesaplar/{hesap_id}/kilit-ac", response_model=HesapSatiri)
async def kilit_ac(
    hesap_id: uuid.UUID, request: Request, ben: Kullanici = Destek, session: AsyncSession = Depends(get_session)
):
    hedef = await _hesap_al(session, hesap_id)
    hedef.kilit_bitis = None
    hedef.basarisiz_deneme = 0
    await audit.kaydet(
        session, "destek_kilit_acildi", kullanici_id=ben.id, hedef_tur="kullanici", hedef_id=str(hedef.id),
        ip=_ip(request), detay={"hedef_rol": hedef.rol.value},
    )
    await session.commit()
    return _satir(hedef, ben.id)


@router.post("/hesaplar/{hesap_id}/sifre-sifirla", response_model=SifreSifirlaYanit)
async def sifre_sifirla(
    hesap_id: uuid.UUID, request: Request, ben: Kullanici = Destek, session: AsyncSession = Depends(get_session)
):
    hedef = await _hesap_al(session, hesap_id)
    if hedef.id == ben.id:
        raise HTTPException(422, KENDI_SIFRESI)
    sifre = gecici_sifre_uret()
    hedef.sifre_ozeti = sifre_ozeti(sifre)
    hedef.sifre_degistirmeli = True
    hedef.basarisiz_deneme = 0
    hedef.kilit_bitis = None
    await _oturumlari_iptal_et(session, hedef.id)
    await audit.kaydet(
        session, "destek_sifre_sifirlandi", kullanici_id=ben.id, hedef_tur="kullanici", hedef_id=str(hedef.id),
        ip=_ip(request), detay={"hedef_rol": hedef.rol.value},
    )
    await session.commit()
    return SifreSifirlaYanit(gecici_sifre=sifre)


@router.post("/hesaplar/{hesap_id}/pasif", response_model=HesapSatiri)
async def pasife_al(
    hesap_id: uuid.UUID, request: Request, ben: Kullanici = Destek, session: AsyncSession = Depends(get_session)
):
    hedef = await _hesap_al(session, hesap_id)
    if hedef.id == ben.id:
        raise HTTPException(422, KENDINI_PASIFE_ALMA)
    if hedef.aktif:
        if hedef.rol == Rol.admin:
            diger = await session.scalar(
                select(func.count(Kullanici.id)).where(
                    Kullanici.rol == Rol.admin, Kullanici.aktif.is_(True), Kullanici.id != hedef.id
                )
            )
            if not diger:
                raise HTTPException(status.HTTP_409_CONFLICT, SON_YONETICI)
        hedef.aktif = False
        await _oturumlari_iptal_et(session, hedef.id)
        await audit.kaydet(
            session, "destek_hesap_pasife_alindi", kullanici_id=ben.id, hedef_tur="kullanici",
            hedef_id=str(hedef.id), ip=_ip(request), detay={"hedef_rol": hedef.rol.value},
        )
        await session.commit()
    return _satir(hedef, ben.id)


@router.post("/hesaplar/{hesap_id}/aktif", response_model=HesapSatiri)
async def aktife_al(
    hesap_id: uuid.UUID, request: Request, ben: Kullanici = Destek, session: AsyncSession = Depends(get_session)
):
    hedef = await _hesap_al(session, hesap_id)
    if not hedef.aktif:
        hedef.aktif = True
        await audit.kaydet(
            session, "destek_hesap_aktife_alindi", kullanici_id=ben.id, hedef_tur="kullanici",
            hedef_id=str(hedef.id), ip=_ip(request), detay={"hedef_rol": hedef.rol.value},
        )
        await session.commit()
    return _satir(hedef, ben.id)


@router.get("/hesaplar/{hesap_id}/oturumlar", response_model=list[OturumSatiri])
async def oturumlari_listele(hesap_id: uuid.UUID, _: Kullanici = Destek, session: AsyncSession = Depends(get_session)):
    if await session.get(Kullanici, hesap_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, BULUNAMADI)
    simdi_ = simdi()
    satirlar = (
        await session.execute(
            select(Oturum).where(Oturum.kullanici_id == hesap_id).order_by(Oturum.olusturma.desc()).limit(50)
        )
    ).scalars()
    return [
        OturumSatiri(
            id=o.id, olusturma=o.olusturma, bitis=o.bitis, hatirla=o.hatirla, aktif=not o.iptal and o.bitis > simdi_
        )
        for o in satirlar
    ]


@router.post("/hesaplar/{hesap_id}/oturumlari-kapat", response_model=OturumKapatYaniti)
async def oturumlari_kapat(
    hesap_id: uuid.UUID, request: Request, ben: Kullanici = Destek, session: AsyncSession = Depends(get_session)
):
    hedef = await _hesap_al(session, hesap_id)
    sonuc = await session.execute(
        update(Oturum).where(Oturum.kullanici_id == hedef.id, Oturum.iptal.is_(False)).values(iptal=True)
    )
    await audit.kaydet(
        session, "destek_oturumlar_kapatildi", kullanici_id=ben.id, hedef_tur="kullanici", hedef_id=str(hedef.id),
        ip=_ip(request), detay={"hedef_rol": hedef.rol.value, "kapatilan": sonuc.rowcount},
    )
    await session.commit()
    return OturumKapatYaniti(kapatilan=sonuc.rowcount)


# --- Bildirim kuyruğu (teknik görünüm) ---


@router.get("/bildirimler", response_model=DestekBildirimListesi)
async def bildirimleri_listele(
    durum: BildirimDurum | None = Query(default=None),
    kanal: BildirimKanal | None = Query(default=None),
    sayfa: int = Query(default=1, ge=1),
    boyut: int = Query(default=20, ge=1, le=100),
    _: Kullanici = Destek,
    session: AsyncSession = Depends(get_session),
):
    kosullar = []
    if durum is not None:
        kosullar.append(Bildirim.durum == durum)
    if kanal is not None:
        kosullar.append(Bildirim.kanal == kanal)
    toplam = (await session.execute(select(func.count()).select_from(Bildirim).where(*kosullar))).scalar_one()
    satirlar = (
        await session.execute(
            select(Bildirim)
            .where(*kosullar)
            .order_by(Bildirim.olusturma.desc(), Bildirim.id.desc())
            .limit(boyut)
            .offset((sayfa - 1) * boyut)
        )
    ).scalars().all()
    kayitlar = [
        DestekBildirimSatiri(
            id=b.id, olusturma=b.olusturma, planli_zaman=b.planli_zaman, gonderim_zamani=b.gonderim_zamani,
            kanal=b.kanal, sablon=b.sablon, durum=b.durum, deneme=b.deneme, hata=b.hata,
            parametreler=b.parametreler, ogrenci_id=b.ogrenci_id, alici_iletisim_id=b.alici_iletisim_id,
            yoklama_id=b.yoklama_id, duyuru_id=b.duyuru_id, metin=await metin_olustur(session, b),
        )
        for b in satirlar
    ]
    return DestekBildirimListesi(kayitlar=kayitlar, toplam=toplam, sayfa=sayfa, boyut=boyut)


async def _toplu_sec(session: AsyncSession, govde: TopluIslemIstegi, uygun: tuple[BildirimDurum, ...]) -> tuple[list[Bildirim], int]:
    """Seçilen kayıtları kilitleyerek alır; durumu uygun olanlar ve atlanan sayısı döner."""
    sorgu = select(Bildirim).with_for_update().order_by(Bildirim.id)
    if govde.tum_hatalilar:
        sorgu = sorgu.where(Bildirim.durum == BildirimDurum.hata)
    else:
        sorgu = sorgu.where(Bildirim.id.in_(set(govde.ids)))
    bulunan = (await session.execute(sorgu)).scalars().all()
    uygunlar = [b for b in bulunan if b.durum in uygun]
    istenen = len(set(govde.ids)) if govde.ids else len(bulunan)
    return uygunlar, istenen - len(uygunlar)


@router.post("/bildirimler/toplu-yeniden-dene", response_model=TopluIslemYaniti)
async def toplu_yeniden_dene(
    govde: TopluIslemIstegi, request: Request, ben: Kullanici = Destek, session: AsyncSession = Depends(get_session)
):
    """Hatalı bildirimleri kuyruğa geri koyar (yalnız `hata` durumundakiler; diğerleri atlanır)."""
    uygunlar, atlanan = await _toplu_sec(session, govde, (BildirimDurum.hata,))
    for b in uygunlar:
        yeniden_denemeye_al(b)
    await audit.kaydet(
        session, "destek_bildirim_toplu_yeniden_denendi", kullanici_id=ben.id, hedef_tur="bildirim",
        ip=_ip(request), detay={"islenen": len(uygunlar), "atlanan": atlanan, "tum_hatalilar": govde.tum_hatalilar},
    )
    await session.commit()
    return TopluIslemYaniti(islenen=len(uygunlar), atlanan=atlanan)


@router.post("/bildirimler/toplu-iptal", response_model=TopluIslemYaniti)
async def toplu_iptal(
    govde: TopluIslemIstegi, request: Request, ben: Kullanici = Destek, session: AsyncSession = Depends(get_session)
):
    """Bekleyen ve hatalı bildirimleri iptal eder (gönderilmiş/iptal edilmiş olanlar atlanır)."""
    uygunlar, atlanan = await _toplu_sec(session, govde, (BildirimDurum.bekliyor, BildirimDurum.hata))
    for b in uygunlar:
        b.durum = BildirimDurum.iptal
    await audit.kaydet(
        session, "destek_bildirim_toplu_iptal", kullanici_id=ben.id, hedef_tur="bildirim",
        ip=_ip(request), detay={"islenen": len(uygunlar), "atlanan": atlanan, "tum_hatalilar": govde.tum_hatalilar},
    )
    await session.commit()
    return TopluIslemYaniti(islenen=len(uygunlar), atlanan=atlanan)
