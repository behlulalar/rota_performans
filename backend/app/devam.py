"""Devam özeti: öğrencinin alınmış yoklamalarından (geldi / gelmedi) hesaplanır.
Yoklaması alınmamış ve iptal edilmiş dersler sayılmaz. Telafiyle girilen dersler de sayılır."""
import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ders_hakki
from app.models.ogrenci import Ogrenci
from app.models.program import DersOturumu, Grup, OgrenciGrup, OturumDurum
from app.models.yoklama import Yoklama, YoklamaDurum
from app.schemas.devam import DevamDersi, DevamOzeti, DevamSatiri, GelmediSebepleri, GrupDevami

SON_GUN = 30
SON_DERS_SAYISI = 10


def _oran(geldi: int, gelmedi: int) -> int | None:
    toplam = geldi + gelmedi
    return round(geldi * 100 / toplam) if toplam else None


def _ozet(satirlar: list[DevamDersi], bugun: date) -> DevamOzeti:
    """`satirlar` en yeniden eskiye sıralıdır."""
    sinir = bugun - timedelta(days=SON_GUN)
    geldi = sum(s.durum == "geldi" for s in satirlar)
    son = [s for s in satirlar if s.tarih > sinir]
    son_geldi = sum(s.durum == "geldi" for s in son)
    ard_arda = 0
    for s in satirlar:
        if s.durum != "gelmedi":
            break
        ard_arda += 1
    sebepler = GelmediSebepleri()
    for s in satirlar:
        if s.durum == "gelmedi":
            alan = s.sebep.value if s.sebep else "bilinmiyor"
            setattr(sebepler, alan, getattr(sebepler, alan) + 1)
    return DevamOzeti(
        katildi=geldi, gelmedi=len(satirlar) - geldi, oran=_oran(geldi, len(satirlar) - geldi),
        gelmedi_sebepleri=sebepler,
        son30_katildi=son_geldi, son30_gelmedi=len(son) - son_geldi, son30_oran=_oran(son_geldi, len(son) - son_geldi),
        ard_arda_gelmedi=ard_arda, son_dersler=satirlar[:SON_DERS_SAYISI],
    )


async def devam_ozetleri(session: AsyncSession, ogrenci_idler: list[uuid.UUID], bugun: date) -> dict[uuid.UUID, DevamOzeti]:
    if not ogrenci_idler:
        return {}
    sorgu = (
        select(Yoklama.ogrenci_id, Yoklama.durum, Yoklama.sebep, Yoklama.aciklama, Yoklama.telafi_mi, DersOturumu.tarih, DersOturumu.baslangic, Grup.ad)
        .join(DersOturumu, DersOturumu.id == Yoklama.oturum_id)
        .join(Grup, Grup.id == DersOturumu.grup_id)
        .where(Yoklama.ogrenci_id.in_(ogrenci_idler), DersOturumu.durum != OturumDurum.iptal)
        .order_by(DersOturumu.tarih.desc(), DersOturumu.baslangic.desc())
    )
    gruplu: dict[uuid.UUID, list[DevamDersi]] = defaultdict(list)
    for oid, durum, sebep, aciklama, telafi, tarih, _, grup_ad in (await session.execute(sorgu)).all():
        gruplu[oid].append(DevamDersi(
            tarih=tarih, durum="geldi" if durum == YoklamaDurum.geldi else "gelmedi", sebep=sebep, aciklama=aciklama if durum == YoklamaDurum.gelmedi else None, telafi_mi=telafi,
            grup_ad=grup_ad,
        ))
    return {oid: _ozet(gruplu[oid], bugun) for oid in ogrenci_idler}


async def grup_devamlari(session: AsyncSession, gruplar: list[Grup], bugun: date) -> list[GrupDevami]:
    """Her grubun şu anki üyeleri (ada göre) ve devam özetleri."""
    if not gruplar:
        return []
    uyeler = (
        await session.execute(
            select(OgrenciGrup.grup_id, Ogrenci.id, Ogrenci.ad, Ogrenci.soyad)
            .join(Ogrenci, Ogrenci.id == OgrenciGrup.ogrenci_id)
            .where(OgrenciGrup.grup_id.in_([g.id for g in gruplar]), OgrenciGrup.bitis.is_(None), Ogrenci.sentetik.is_(False))
            .order_by(Ogrenci.ad, Ogrenci.soyad, Ogrenci.id)
        )
    ).all()
    idler = list({u[1] for u in uyeler})
    ozetler = await devam_ozetleri(session, idler, bugun)
    bakiyeler = await ders_hakki.bakiyeler(session, idler)
    return [
        GrupDevami(
            grup_id=g.id, grup_ad=g.ad,
            ogrenciler=[DevamSatiri(ogrenci_id=oid, ad=ad, soyad=soyad, devam=ozetler[oid], telafi_bakiyesi=max(bakiyeler[oid]['telafi'], 0)) for gid, oid, ad, soyad in uyeler if gid == g.id],
        )
        for g in gruplar
    ]
