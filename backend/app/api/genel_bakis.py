from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import rol_gerekli
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import IletisimKisisi, Ogrenci, OgrenciDurum
from app.models.paket import OgrenciPaketi, OgrenciPaketiDurum
from app.models.program import Antrenor, Grup, GrupProgrami, OgrenciGrup
from app.schemas.genel_bakis import (
    AntrenorSayisi,
    BekleyenOdeme,
    GenelBakisYanit,
    GrupDolulugu,
    GrupOzeti,
    OgrenciSayilari,
    ProgramSlotu,
    SonKayit,
)

router = APIRouter(prefix="/api/genel-bakis", tags=["genel-bakis"])

Yonetici = Depends(rol_gerekli(Rol.admin))

DOLULUK_LISTESI_SINIRI = 10
SON_KAYIT_SAYISI = 5


@router.get("", response_model=GenelBakisYanit)
async def getir(_: Kullanici = Yonetici, session: AsyncSession = Depends(get_session)):
    bugun = date.today()
    ay_basi = bugun.replace(day=1)
    ay_sonu = date(bugun.year + (bugun.month == 12), bugun.month % 12 + 1, 1)

    gercek = Ogrenci.sentetik.is_(False)
    aktif = Ogrenci.durum == OgrenciDurum.aktif

    hesapli_birincil = exists().where(
        IletisimKisisi.ogrenci_id == Ogrenci.id,
        IletisimKisisi.birincil.is_(True),
        IletisimKisisi.kullanici_id.is_not(None),
    )
    acik_uyelik = exists().where(
        OgrenciGrup.ogrenci_id == Ogrenci.id,
        OgrenciGrup.bitis.is_(None),
        OgrenciGrup.grup_id.in_(select(Grup.id).where(Grup.aktif.is_(True))),
    )

    def sayac(kosul):
        return func.count().filter(kosul)

    ogrenci_satiri = (
        await session.execute(
            select(
                sayac(aktif),
                sayac(Ogrenci.durum == OgrenciDurum.pasif),
                sayac(and_(aktif, Ogrenci.kayit_tarihi >= ay_basi, Ogrenci.kayit_tarihi < ay_sonu)),
                sayac(and_(aktif, ~hesapli_birincil)),
                sayac(and_(aktif, ~acik_uyelik)),
            ).where(gercek)
        )
    ).one()

    sayilar = (
        select(OgrenciGrup.grup_id, func.count().label("sayi"))
        .join(Ogrenci, Ogrenci.id == OgrenciGrup.ogrenci_id)
        .where(OgrenciGrup.bitis.is_(None), Ogrenci.sentetik.is_(False))
        .group_by(OgrenciGrup.grup_id)
        .subquery()
    )
    grup_satirlari = (
        await session.execute(
            select(Grup.id, Grup.ad, Grup.kontenjan, func.coalesce(sayilar.c.sayi, 0))
            .outerjoin(sayilar, sayilar.c.grup_id == Grup.id)
            .where(Grup.aktif.is_(True))
        )
    ).all()
    liste = sorted(
        (GrupDolulugu(id=i, ad=ad, kontenjan=k, ogrenci_sayisi=s) for i, ad, k, s in grup_satirlari),
        key=lambda g: (-g.ogrenci_sayisi / g.kontenjan, g.ad, str(g.id)),
    )

    gosterilen = liste[:DOLULUK_LISTESI_SINIRI]
    # Programlar tek sorguda alınır (N+1 yok); gün ve saat sırasıyla.
    programlar: dict = {g.id: [] for g in gosterilen}
    if gosterilen:
        program_satirlari = (
            await session.execute(
                select(GrupProgrami.grup_id, GrupProgrami.gun, GrupProgrami.baslangic, GrupProgrami.bitis)
                .where(GrupProgrami.grup_id.in_(programlar))
                .order_by(GrupProgrami.gun, GrupProgrami.baslangic)
            )
        ).all()
        for grup_id, gun, baslangic, bitis in program_satirlari:
            programlar[grup_id].append(ProgramSlotu(gun=gun, baslangic=baslangic, bitis=bitis))
        for g in gosterilen:
            g.program = programlar[g.id]

    antrenor_sayisi = (await session.execute(select(func.count()).where(Antrenor.aktif.is_(True)))).scalar_one()

    adet, toplam = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(OgrenciPaketi.uygulanan_fiyat), 0))
            .join(Ogrenci, Ogrenci.id == OgrenciPaketi.ogrenci_id)
            .where(OgrenciPaketi.durum == OgrenciPaketiDurum.odeme_bekliyor, gercek)
        )
    ).one()

    son = (
        await session.execute(
            select(Ogrenci)
            .where(gercek, aktif)
            .order_by(Ogrenci.olusturma.desc(), Ogrenci.id)
            .limit(SON_KAYIT_SAYISI)
        )
    ).scalars()

    return GenelBakisYanit(
        ogrenci=OgrenciSayilari(aktif=ogrenci_satiri[0], pasif=ogrenci_satiri[1], bu_ay_kayit=ogrenci_satiri[2]),
        hesapsiz_aktif_ogrenci=ogrenci_satiri[3],
        grupsuz_aktif_ogrenci=ogrenci_satiri[4],
        gruplar=GrupOzeti(
            aktif_grup=len(liste),
            toplam_kontenjan=sum(g.kontenjan for g in liste),
            dolu=sum(g.ogrenci_sayisi for g in liste),
            doluluk_listesi=gosterilen,
        ),
        antrenor=AntrenorSayisi(aktif=antrenor_sayisi),
        bekleyen_odeme=BekleyenOdeme(adet=adet, toplam_tutar=f"{Decimal(toplam):.2f}"),
        son_kayitlar=[
            SonKayit(id=o.id, ad=o.ad, soyad=o.soyad, kayit_tarihi=o.kayit_tarihi, foto_var=o.foto_anahtar is not None)
            for o in son
        ],
    )
