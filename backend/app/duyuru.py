"""Elle yazılan duyurular: hedef kitleyi çözer, alıcıları belirler, bildirim kuyruğuna yazar.

Kurallar:
- Alıcı her öğrencinin birincil iletişim kişisidir. Aynı hesabı (kullanici_id) ya da aynı telefonu
  paylaşan kardeşler tek alıcıdır: kanal başına BİR bildirim gider (`ogrenci_id` ilk öğrencidir,
  sıra soyad, ad, id).
- Duyurular tür tercihlerine (`ders_gelmedi`, `ders_hakki`) tabi DEĞİLDİR; kanal tercihlerine tabidir:
  push için hesap + `BildirimTercihi.push` + kayıtlı en az bir cihaz, WhatsApp için `whatsapp_izni` +
  `BildirimTercihi.whatsapp`. Tercih satırı yoksa kanallar açıktır.
- WhatsApp henüz gönderilmez (Evolution API sonra); API bu kanalı reddeder.
Çağıran işlemi commit eder."""
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.bildirim import DUYURU
from app.models.bildirim import Bildirim, BildirimDurum, BildirimKanal, BildirimTercihi, PushAbonelik
from app.models.duyuru import Duyuru, DuyuruHedefTuru
from app.models.ogrenci import IletisimKisisi, Ogrenci, OgrenciDurum
from app.models.program import DersOturumu, Grup, OgrenciGrup, TelafiPlani
from app.oturumlar import bugun


class HedefHatasi(ValueError):
    """Hedef geçersiz (oturum ya da grup bulunamadı)."""


@dataclass
class Kitle:
    ogrenci_idleri: list[uuid.UUID]  # soyad, ad, id sırasıyla
    push: list[tuple[uuid.UUID, IletisimKisisi]] = field(default_factory=list)  # (ilk öğrenci, kişi)
    whatsapp: list[tuple[uuid.UUID, IletisimKisisi]] = field(default_factory=list)
    alici_sayisi: int = 0  # birincil kişisi olan, tekilleştirilmiş alıcılar


async def hedef_ogrencileri(
    session: AsyncSession, tur: DuyuruHedefTuru, *, oturum_id: uuid.UUID | None = None,
    grup_idleri: list[uuid.UUID] | None = None,
) -> list[uuid.UUID]:
    """Hedefteki AKTİF öğrencilerin kimlikleri (soyad, ad, id sırasıyla, tekrarsız)."""
    sorgu = select(Ogrenci.id).where(Ogrenci.durum == OgrenciDurum.aktif, Ogrenci.sentetik.is_(False))
    if tur == DuyuruHedefTuru.oturum:
        oturum = await session.get(DersOturumu, oturum_id) if oturum_id else None
        if oturum is None:
            raise HedefHatasi("Ders oturumu bulunamadı")
        uye = select(OgrenciGrup.ogrenci_id).where(
            OgrenciGrup.grup_id == oturum.grup_id,
            OgrenciGrup.baslangic <= oturum.tarih,
            or_(OgrenciGrup.bitis.is_(None), OgrenciGrup.bitis >= oturum.tarih),
        )
        telafi = select(TelafiPlani.ogrenci_id).where(TelafiPlani.oturum_id == oturum.id)
        sorgu = sorgu.where(or_(Ogrenci.id.in_(uye), Ogrenci.id.in_(telafi)))
    elif tur == DuyuruHedefTuru.grup:
        idler = list(dict.fromkeys(grup_idleri or []))
        if not idler:
            raise HedefHatasi("En az bir grup seçin")
        var = set((await session.execute(select(Grup.id).where(Grup.id.in_(idler)))).scalars())
        if var != set(idler):
            raise HedefHatasi("Grup bulunamadı")
        t = bugun()
        uye = select(OgrenciGrup.ogrenci_id).where(
            OgrenciGrup.grup_id.in_(idler),
            OgrenciGrup.baslangic <= t,
            or_(OgrenciGrup.bitis.is_(None), OgrenciGrup.bitis >= t),
        )
        sorgu = sorgu.where(Ogrenci.id.in_(uye))
    return list(
        (await session.execute(sorgu.order_by(Ogrenci.soyad, Ogrenci.ad, Ogrenci.id))).scalars()
    )


def _anahtar(kisi: IletisimKisisi) -> str:
    """Aynı alıcıyı tanıyan anahtar: panel hesabı, yoksa telefon."""
    return f"h:{kisi.kullanici_id}" if kisi.kullanici_id is not None else f"t:{kisi.telefon}"


async def kitleyi_coz(
    session: AsyncSession, tur: DuyuruHedefTuru, *, oturum_id: uuid.UUID | None = None,
    grup_idleri: list[uuid.UUID] | None = None,
) -> Kitle:
    idler = await hedef_ogrencileri(session, tur, oturum_id=oturum_id, grup_idleri=grup_idleri)
    kitle = Kitle(ogrenci_idleri=idler)
    if not idler:
        return kitle
    kisiler = {
        k.ogrenci_id: k
        for k in (
            await session.execute(
                select(IletisimKisisi).where(IletisimKisisi.ogrenci_id.in_(idler), IletisimKisisi.birincil.is_(True))
            )
        ).scalars()
    }
    hesaplar = {k.kullanici_id for k in kisiler.values() if k.kullanici_id is not None}
    tercihler: dict[uuid.UUID, BildirimTercihi] = {}
    cihazli: set[uuid.UUID] = set()
    if hesaplar:
        tercihler = {
            t.kullanici_id: t
            for t in (
                await session.execute(select(BildirimTercihi).where(BildirimTercihi.kullanici_id.in_(hesaplar)))
            ).scalars()
        }
        cihazli = set(
            (await session.execute(select(PushAbonelik.kullanici_id).where(PushAbonelik.kullanici_id.in_(hesaplar))))
            .scalars()
        )

    def push_uygun(k: IletisimKisisi) -> bool:
        if k.kullanici_id is None or k.kullanici_id not in cihazli:
            return False
        t = tercihler.get(k.kullanici_id)
        return t is None or t.push

    def whatsapp_uygun(k: IletisimKisisi) -> bool:
        if not k.whatsapp_izni:
            return False
        t = tercihler.get(k.kullanici_id) if k.kullanici_id is not None else None
        return t is None or t.whatsapp

    gorulen: set[str] = set()
    push_gorulen: set[str] = set()
    wa_gorulen: set[str] = set()
    for oid in idler:
        k = kisiler.get(oid)
        if k is None:
            continue
        a = _anahtar(k)
        if a not in gorulen:
            gorulen.add(a)
            kitle.alici_sayisi += 1
        # Her kanalda o kanala uygun ilk kişi seçilir (kardeşlerden biri uygun değilse diğeri alır).
        if a not in push_gorulen and push_uygun(k):
            push_gorulen.add(a)
            kitle.push.append((oid, k))
        if a not in wa_gorulen and whatsapp_uygun(k):
            wa_gorulen.add(a)
            kitle.whatsapp.append((oid, k))
    return kitle


async def kuyruga_ekle(session: AsyncSession, duyuru: Duyuru, kitle: Kitle, simdi: datetime) -> dict[str, int]:
    """Duyuru kanallarına göre bildirim satırlarını yazar; kanal başına eklenen sayıyı verir.
    (duyuru, alıcı kişi, kanal) çifti tekrar yazılmaz."""
    secimler = []
    if duyuru.kanal_push:
        secimler.append((BildirimKanal.push, kitle.push))
    if duyuru.kanal_whatsapp:
        secimler.append((BildirimKanal.whatsapp, kitle.whatsapp))
    eklenen: dict[str, int] = {}
    for kanal, alicilar in secimler:
        n = 0
        for ogrenci_id, kisi in alicilar:
            sonuc = await session.execute(
                insert(Bildirim)
                .values(
                    ogrenci_id=ogrenci_id, alici_iletisim_id=kisi.id, kanal=kanal, sablon=DUYURU,
                    parametreler={"duyuru_id": str(duyuru.id)}, duyuru_id=duyuru.id,
                    durum=BildirimDurum.bekliyor, planli_zaman=simdi, deneme=0,
                )
                .on_conflict_do_nothing(
                    index_elements=["duyuru_id", "alici_iletisim_id", "kanal"],
                    index_where=Bildirim.duyuru_id.is_not(None),
                )
            )
            n += sonuc.rowcount
        eklenen[kanal.value] = n
    return eklenen
