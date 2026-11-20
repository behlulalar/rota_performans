"""Geliştirme veritabanı için gerçekçi örnek (mock) veri.

Yalnızca ENV=dev iken çalışır; var olan veriye dokunmaz, yalnızca ekler. İkinci çalıştırmada
örnek antrenörlerden biri zaten varsa "zaten yüklü" der ve çıkar. Ders hakkı bakiyeleri defterden
türetilir: doğrudan bakiye yazılmaz, yoklama ve düzeltme hareketleri ders_hakki modülüyle üretilir.
"""
import itertools
from decimal import Decimal
import random
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app import ders_hakki, kimlik
from app.config import settings
from app.db import SessionLocal
from app.models.kullanici import Kullanici, Rol
from app.models.ogrenci import (
    Cinsiyet,
    IletisimKisisi,
    IletisimRolu,
    KimlikTur,
    Ogrenci,
    OgrenciDurum,
    Riza,
    RizaTuru,
)
from app.models.paket import Odeme, OdemeYontemi, OgrenciPaketi, OgrenciPaketiDurum, Paket, PaketTuru
from app.models.program import Antrenor, DersOturumu, Grup, GrupProgrami, OgrenciGrup, OturumDurum, TelafiPlani
from app.models.yoklama import DersHakkiHareketi, DevamsizlikSebebi, HareketTuru, Sayac, YoklamaDurum
from app.oturumlar import bugun as bugun_fn
from app.oturumlar import oturumlari_uret
from app.security import sifre_ozeti

# Örnek devamsızlıkların sebep dağılımı: çoğu mazeretli, bir kısmı habersiz.
ORNEK_SEBEPLER = [DevamsizlikSebebi.izinli] * 4 + [DevamsizlikSebebi.raporlu] * 2 + [
    DevamsizlikSebebi.yarisma, DevamsizlikSebebi.devamsiz, DevamsizlikSebebi.devamsiz,
]

SIFRE = "Ornek-Sifre-2026"
GECMIS_GUN = 28
GELECEK_GUN = 14

ANTRENORLER = [
    ("Mehmet Kaya", "+905323000001"),
    ("Ayşe Demir", "+905323000002"),
    ("Burak Şahin", "+905323000003"),
    ("Elif Yıldız", "+905323000004"),
]

# ad, antrenör sırası, kontenjan, [(gün, başlangıç, süre dk)]
GRUPLAR = [
    ("Minikler A", 1, 12, [(1, "17:00", 60), (3, "17:00", 60)]),
    ("Minikler B", 1, 12, [(2, "17:30", 60), (4, "17:30", 60)]),
    ("Gençler", 2, 16, [(1, "18:30", 90), (3, "18:30", 90), (5, "18:30", 90)]),
    ("Yetişkin Başlangıç", 3, 14, [(2, "20:00", 60), (4, "20:00", 60)]),
    ("Performans", 0, 14, [(2, "19:00", 90), (4, "19:00", 90), (6, "09:00", 90)]),
    ("Hafta Sonu", 3, 20, [(6, "10:30", 90), (7, "10:30", 90)]),
]

ERKEK = ["Ahmet", "Mehmet", "Mustafa", "Emir", "Yusuf", "Kerem", "Ali", "Can", "Efe", "Arda", "Berk",
         "Deniz", "Kaan", "Onur", "Burak", "Cem", "Eren", "Barış", "Ozan", "Tolga"]
KADIN = ["Zeynep", "Elif", "Defne", "Ecrin", "Asya", "Azra", "Ela", "Nehir", "Melisa", "Ceren",
         "Selin", "Ayşe", "Fatma", "Buse", "İrem", "Duru", "Naz", "Sude", "Derya", "Esra"]
SOYADLAR = ["Yılmaz", "Kaya", "Demir", "Çelik", "Şahin", "Yıldız", "Öztürk", "Aydın", "Özdemir", "Arslan",
            "Doğan", "Kılıç", "Aslan", "Çetin", "Kara", "Koç", "Kurt", "Özkan", "Şimşek", "Polat",
            "Erdoğan", "Güneş", "Aksoy", "Korkmaz", "Tekin", "Bulut", "Avcı", "Çakır", "Acar", "Türk"]

# Her öğrencinin ders paketinde kalan hak hedefi (liste çeşitli görünsün).
KALAN_DESENI = [6, 4, 8, 2, 0, 5, 3, 7, 1, 4, 0, 6, 2, 8, 3]


class OrnekVeriHatasi(Exception):
    pass


def _tc_uret(rng: random.Random, kullanilan: set[str]) -> str:
    while True:
        d = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(8)]
        d10 = ((sum(d[0:9:2]) * 7) - sum(d[1:8:2])) % 10
        d.append(d10)
        d.append(sum(d) % 10)
        no = "".join(map(str, d))
        if kimlik.tc_gecerli_mi(no) and no not in kullanilan:
            kullanilan.add(no)
            return no


def _dogum(bugun: date, yas: int, rng: random.Random) -> date:
    return bugun.replace(year=bugun.year - yas) - timedelta(days=rng.randint(1, 300))


def _ogrenci_planla(rng: random.Random, bugun: date) -> list[dict]:
    """Öğrenci ve aile tanımlarını belirleyici (sabit tohumlu) üretir."""
    kullanilan_ad: set[tuple[str, str]] = set()

    def ad_sec(cins: Cinsiyet, soyad: str) -> str:
        havuz = ERKEK if cins == Cinsiyet.erkek else KADIN
        while True:
            ad = rng.choice(havuz)
            if (ad, soyad) not in kullanilan_ad:
                kullanilan_ad.add((ad, soyad))
                return ad

    soyadlar = SOYADLAR[:]
    rng.shuffle(soyadlar)
    sira = itertools.cycle(soyadlar)
    plan: list[dict] = []

    def aile(soyad: str) -> dict:
        return {"soyad": soyad, "anne": rng.choice(KADIN), "baba": rng.choice(ERKEK)}

    # 3 kardeş çifti (çocuk), aynı veli hesabı.
    for yaslar in [(6, 9), (8, 11), (12, 15)]:
        a = aile(next(sira))
        kimlik_grup = f"kardes-{a['soyad']}"
        for yas in yaslar:
            cins = rng.choice([Cinsiyet.erkek, Cinsiyet.kadin])
            plan.append({"yas": yas, "cins": cins, "ad": ad_sec(cins, a["soyad"]), "aile": a, "kardes": kimlik_grup})
    # Tek çocuklar: 26 çocuk, 5-17 arası, 5-6 yaş birkaç tane.
    cocuk_yaslar = [5, 5, 5, 6, 6, 6, 7, 7, 7, 8, 8, 9, 9, 10, 10, 10, 11, 12, 12, 13, 13, 14, 14, 15, 16, 17]
    for yas in cocuk_yaslar:
        a = aile(next(sira))
        cins = rng.choice([Cinsiyet.erkek, Cinsiyet.kadin])
        plan.append({"yas": yas, "cins": cins, "ad": ad_sec(cins, a["soyad"]), "aile": a, "kardes": None})
    # 8 reşit: biri uyarı örneği (19 yaşında, birincil iletişim hâlâ veli).
    for sira_no, yas in enumerate([19, 22, 25, 28, 31, 35, 38, 40]):
        a = aile(next(sira))
        cins = rng.choice([Cinsiyet.erkek, Cinsiyet.kadin])
        plan.append({
            "yas": yas, "cins": cins, "ad": ad_sec(cins, a["soyad"]), "aile": a, "kardes": None,
            "resit": True, "uyari": sira_no == 0, "hesap": sira_no in (1, 2),
        })
    return plan


def _gruplari_ata(rng: random.Random, plan: list[dict]) -> None:
    for o in plan:
        yas = o["yas"]
        if yas <= 8:
            gruplar = ["Minikler A"]
        elif yas <= 11:
            gruplar = ["Minikler B"]
        elif yas <= 17:
            gruplar = [rng.choice(["Gençler", "Performans"])]
            if rng.random() < 0.3:
                gruplar = ["Gençler", "Performans"]
        else:
            gruplar = ["Yetişkin Başlangıç"]
        if "Hafta Sonu" not in gruplar and rng.random() < 0.3 and len(gruplar) == 1:
            gruplar.append("Hafta Sonu")
        o["gruplar"] = gruplar


async def _zaten_yuklu(session) -> bool:
    return (
        await session.execute(select(Kullanici.id).where(Kullanici.giris == ANTRENORLER[0][1]))
    ).first() is not None


def _kulup_zamani(tarih: date, saat: time) -> datetime:
    return datetime.combine(tarih, saat, tzinfo=ZoneInfo(settings.saat_dilimi)).astimezone(timezone.utc)


async def yukle() -> int:
    if settings.env not in ("dev", "demo"):
        print(f"ornek-veri yalnızca ENV=dev veya ENV=demo iken çalışır (şu an ENV={settings.env}).")
        return 1
    rng = random.Random(2026)
    bugun = bugun_fn()
    simdi = datetime.now(timezone.utc)
    sifre_hash = sifre_ozeti(SIFRE)

    async with SessionLocal() as session:
        if await _zaten_yuklu(session):
            print("Örnek veri zaten yüklü (örnek antrenör hesapları var). Hiçbir şey eklenmedi.")
            return 0
        try:
            ozet = await _ekle(session, rng, bugun, simdi, sifre_hash)
            await session.commit()
        except IntegrityError as hata:
            await session.rollback()
            print(f"Örnek veri eklenemedi, çakışma var (hiçbir şey kaydedilmedi): {hata.orig}")
            return 1

    print("Örnek veri yüklendi.")
    for anahtar, deger in ozet["sayilar"].items():
        print(f"  {anahtar}: {deger}")
    print("Örnek giriş bilgileri (hepsinin şifresi aynı):")
    print(f"  Şifre: {SIFRE}")
    for etiket, giris in ozet["girisler"]:
        print(f"  {etiket}: {giris}")
    return 0


async def _ekle(session, rng, bugun: date, simdi: datetime, sifre_hash: str) -> dict:
    # ---------- antrenörler ----------
    antrenorler: list[Antrenor] = []
    antrenor_kullanici: dict[uuid.UUID, uuid.UUID] = {}
    for ad, tel in ANTRENORLER:
        k = Kullanici(rol=Rol.antrenor, giris=tel, sifre_ozeti=sifre_hash, ad_soyad=ad, sifre_degistirmeli=False)
        session.add(k)
        await session.flush()
        a = Antrenor(kullanici_id=k.id, ad_soyad=ad, telefon=tel, aktif=True)
        session.add(a)
        await session.flush()
        antrenorler.append(a)
        antrenor_kullanici[a.id] = k.id

    # ---------- gruplar ve programlar ----------
    gruplar: dict[str, Grup] = {}
    for ad, a_sira, kontenjan, slotlar in GRUPLAR:
        g = Grup(ad=ad, antrenor_id=antrenorler[a_sira].id, kontenjan=kontenjan, aktif=True)
        session.add(g)
        await session.flush()
        gruplar[ad] = g
        for gun, bas, sure in slotlar:
            b = time.fromisoformat(bas)
            bitis = (datetime.combine(bugun, b) + timedelta(minutes=sure)).time()
            session.add(GrupProgrami(grup_id=g.id, gun=gun, baslangic=b, bitis=bitis))
    await session.flush()

    # ---------- öğrenciler ----------
    plan = _ogrenci_planla(rng, bugun)
    _gruplari_ata(rng, plan)
    tc_kullanilan: set[str] = set()
    veli_hesaplari: dict[str, Kullanici] = {}  # kardeş anahtarı -> ortak veli hesabı
    ogr_tel = iter(range(1, 1000))
    veli_tel = iter(range(1, 1000))
    ogrenciler: list[tuple[Ogrenci, dict]] = []
    veli_ornek = resit_ornek = None
    veli_hesap_sayisi = 0
    pasif_sirasi = {5, 14, 22, 31}  # çocuk/reşit karışık 4 pasif
    # Rıza eksikliği: belirli sıralarda.
    for i, o in enumerate(plan):
        a = o["aile"]
        resit = o.get("resit", False)
        ogrenci_tel = f"+90555100{next(ogr_tel):04d}" if (resit or o["yas"] >= 13 or rng.random() < 0.2) else None
        if resit and ogrenci_tel is None:
            raise OrnekVeriHatasi("reşit için telefon")
        no = _tc_uret(rng, tc_kullanilan)
        durum = OgrenciDurum.pasif if i in pasif_sirasi else OgrenciDurum.aktif
        ogr = Ogrenci(
            ad=o["ad"], soyad=a["soyad"], anne_adi=a["anne"], baba_adi=a["baba"],
            dogum_tarihi=_dogum(bugun, o["yas"], rng), cinsiyet=o["cins"],
            kimlik_tur=KimlikTur.tc, kimlik_no_sifreli=kimlik.sifrele(no), kimlik_no_ozet=kimlik.ozet(no),
            telefon=ogrenci_tel, durum=durum, kayit_tarihi=bugun - timedelta(days=rng.randint(60, 600)),
            sentetik=False,
        )
        session.add(ogr)
        await session.flush()
        ogrenciler.append((ogr, o))

        riza_aydinlatma = rng.random() > 0.08
        riza_whatsapp = rng.random() > 0.25
        riza_foto = rng.random() > 0.35
        if i in (2, 17):
            riza_aydinlatma = False  # KVKK eksik
        birincil_id = None
        if resit and not o.get("uyari"):
            kisi = IletisimKisisi(
                ogrenci_id=ogr.id, rol=IletisimRolu.kendisi, ad_soyad=f"{ogr.ad} {ogr.soyad}",
                telefon=ogrenci_tel, birincil=True, whatsapp_izni=riza_whatsapp,
            )
            if o.get("hesap"):
                k = Kullanici(rol=Rol.ogrenci, giris=ogrenci_tel, sifre_ozeti=sifre_hash,
                              ad_soyad=f"{ogr.ad} {ogr.soyad}", sifre_degistirmeli=False)
                session.add(k)
                await session.flush()
                ogr.kullanici_id = k.id
                if resit_ornek is None:
                    resit_ornek = (f"Reşit öğrenci ({ogr.ad} {ogr.soyad})", ogrenci_tel)
            session.add(kisi)
            await session.flush()
            birincil_id = kisi.id
        else:
            # Çocuk (veya uyarı örneği olan reşit): anne + baba, biri birincil.
            kardes = o.get("kardes")
            if kardes and kardes + ":kisiler" in veli_hesaplari:
                anne_birincil = veli_hesaplari[kardes + ":kisiler"]["anne_birincil"]
            else:
                anne_birincil = bool(rng.random() < 0.65 or o.get("uyari"))
            anne = IletisimKisisi(
                ogrenci_id=ogr.id, rol=IletisimRolu.anne, ad_soyad=f"{a['anne']} {a['soyad']}",
                telefon="", birincil=anne_birincil, whatsapp_izni=anne_birincil and riza_whatsapp,
            )
            baba = IletisimKisisi(
                ogrenci_id=ogr.id, rol=IletisimRolu.baba, ad_soyad=f"{a['baba']} {a['soyad']}",
                telefon="", birincil=not anne_birincil, whatsapp_izni=(not anne_birincil) and riza_whatsapp,
            )
            if kardes and kardes + ":kisiler" in veli_hesaplari:
                # Kardeşin telefonlarını aynen kullan (aynı veli).
                ref = veli_hesaplari[kardes + ":kisiler"]
                anne.telefon, baba.telefon = ref["anne"], ref["baba"]
            else:
                anne.telefon = f"+90533200{next(veli_tel):04d}"
                baba.telefon = f"+90533200{next(veli_tel):04d}"
                if kardes:
                    veli_hesaplari[kardes + ":kisiler"] = {"anne": anne.telefon, "baba": baba.telefon, "anne_birincil": anne_birincil}
            birincil_kisi = anne if anne_birincil else baba
            # Çocukların ~%75'inin (kardeşlerin hepsinin) veli hesabı var; uyarı örneğinde de var.
            hesap_ister = bool(kardes) or o.get("uyari") or (i % 4 != 0)
            if hesap_ister:
                anahtar = kardes
                k = veli_hesaplari.get(anahtar) if anahtar else None
                if k is None:
                    k = Kullanici(rol=Rol.veli, giris=birincil_kisi.telefon, sifre_ozeti=sifre_hash,
                                  ad_soyad=birincil_kisi.ad_soyad, sifre_degistirmeli=False)
                    session.add(k)
                    await session.flush()
                    veli_hesap_sayisi += 1
                    if anahtar:
                        veli_hesaplari[anahtar] = k
                    if veli_ornek is None and not anahtar and not o.get("uyari"):
                        veli_ornek = (f"Veli ({birincil_kisi.ad_soyad}, çocuk {ogr.ad} {ogr.soyad})", k.giris)
                # Kardeşte birincil kişi aynı kişi olmalı (aynı hesap): anne/baba seçimi ilk kardeşten gelsin.
                birincil_kisi.kullanici_id = k.id
                if k.giris != birincil_kisi.telefon:
                    raise OrnekVeriHatasi("kardeş birincil kişi uyuşmuyor")
            if o.get("uyari"):
                ogr.telefon = ogrenci_tel
            session.add_all([anne, baba])
            await session.flush()
            birincil_id = birincil_kisi.id
        for tur, verildi in (
            (RizaTuru.aydinlatma, riza_aydinlatma), (RizaTuru.whatsapp, riza_whatsapp), (RizaTuru.foto, riza_foto)
        ):
            if verildi:
                session.add(Riza(ogrenci_id=ogr.id, iletisim_kisisi_id=birincil_id, tur=tur))

    # ---------- üyelikler ----------
    uyelik_bas = bugun - timedelta(days=90)
    uyeler: dict[str, list[Ogrenci]] = defaultdict(list)
    for ogr, o in ogrenciler:
        pasif = ogr.durum == OgrenciDurum.pasif
        for g in o["gruplar"]:
            session.add(OgrenciGrup(
                ogrenci_id=ogr.id, grup_id=gruplar[g].id, baslangic=uyelik_bas,
                bitis=bugun - timedelta(days=40) if pasif else None,
            ))
            if not pasif:
                uyeler[g].append(ogr)
    await session.flush()
    for ad, liste in uyeler.items():
        if len(liste) > gruplar[ad].kontenjan:
            raise OrnekVeriHatasi(f"{ad} kontenjanı aşıldı")

    # ---------- oturumlar ----------
    grup_idleri = [g.id for g in gruplar.values()]
    await oturumlari_uret(session, bugun - timedelta(days=GECMIS_GUN), bugun + timedelta(days=GELECEK_GUN), grup_idleri)
    oturumlar = list(
        (await session.execute(
            select(DersOturumu).where(DersOturumu.grup_id.in_(grup_idleri)).order_by(DersOturumu.tarih, DersOturumu.baslangic)
        )).scalars()
    )
    gecmis = [
        s for s in oturumlar
        if _kulup_zamani(s.tarih, s.bitis) <= simdi
    ]
    gelecek = [s for s in oturumlar if _kulup_zamani(s.tarih, s.bitis) > simdi]
    # Geçmişte 2 ders iptal (yoklaması yok), bir derste yerine bakan antrenör.
    iptaller = {s.id for s in rng.sample(gecmis[3:], 2)}
    yerine = rng.choice([s for s in gecmis[3:] if s.id not in iptaller])
    yerine.antrenor_id = antrenorler[3].id if gruplar_antrenor(gruplar, yerine) != antrenorler[3].id else antrenorler[2].id
    for s in gecmis:
        s.durum = OturumDurum.iptal if s.id in iptaller else OturumDurum.yapildi

    # ---------- yoklama (geçmiş) ----------
    uye_ids_by_grup = {gruplar[ad].id: [o.id for o in liste] for ad, liste in uyeler.items()}
    zorunlu_gelmedi = {}  # telafi örneği öğrencileri: ilk iki geçmiş dersine gelmedi
    aktifler = [(o, d) for o, d in ogrenciler if o.durum == OgrenciDurum.aktif]
    telafi_ogrenciler = [aktifler[3][0], aktifler[10][0], aktifler[20][0], aktifler[27][0]]
    for o in telafi_ogrenciler:
        zorunlu_gelmedi[o.id] = True
    tuketim: dict[uuid.UUID, int] = defaultdict(int)
    gelmedi_sayisi: dict[uuid.UUID, int] = defaultdict(int)
    # Öğrenci başına devam eğilimi: çoğu düzenli, bazıları sık gelmeyen.
    egilim = {o.id: rng.choice([0.95, 0.9, 0.85, 0.8, 0.7, 0.55]) for o, _ in aktifler}
    yoklama_sayisi = 0
    for s in gecmis:
        if s.id in iptaller:
            continue
        isaretleyen = antrenor_kullanici[s.antrenor_id or _grup_antrenor(gruplar, s.grup_id)]
        an = _kulup_zamani(s.tarih, s.bitis)
        for ogr_id in uye_ids_by_grup.get(s.grup_id, []):
            if ogr_id in zorunlu_gelmedi and tuketim[ogr_id] < 2:
                geldi = False
            else:
                geldi = rng.random() < egilim[ogr_id]
            await ders_hakki.yoklama_olustur(
                session, oturum_id=s.id, ogrenci_id=ogr_id,
                durum=YoklamaDurum.geldi if geldi else YoklamaDurum.gelmedi,
                telafi_mi=False, isaretleyen_id=isaretleyen, simdi=an,
                sebep=None if geldi else rng.choice(ORNEK_SEBEPLER),
            )
            tuketim[ogr_id] += 1
            if not geldi:
                gelmedi_sayisi[ogr_id] += 1
            yoklama_sayisi += 1
    # 1 saati dolanların devamsızlık (telafi) hareketleri mevcut işçi mantığıyla.
    devamsizlik_islenen = await ders_hakki.bekleyen_devamsizliklari_isle(session, simdi)

    # ---------- ders yüklemeleri (defter) ----------
    kalan_iter = iter(KALAN_DESENI * 4)
    yukleme_zamani = simdi - timedelta(days=GECMIS_GUN + 2)
    for ogr, _ in aktifler:
        kalan = next(kalan_iter)
        toplam = tuketim[ogr.id] + kalan
        if toplam <= 0:
            continue
        parcalar = [8] * (toplam // 8) + ([toplam % 8] if toplam % 8 else [])
        for n, miktar in enumerate(parcalar):
            session.add(DersHakkiHareketi(
                ogrenci_id=ogr.id, sayac=Sayac.normal, miktar=miktar, tur=HareketTuru.manuel_duzeltme,
                neden=f"Aylık ders paketi yüklemesi ({miktar} ders) - örnek veri",
                zaman=yukleme_zamani + timedelta(days=10 * n), olusturan_id=None,
            ))
    await session.flush()

    # ---------- planlı telafi dersleri ----------
    telafi_sayisi = 0
    plan_by_id = {o.id: d for o, d in ogrenciler}
    for ogr in telafi_ogrenciler:
        o_gruplari = {gruplar[g].id for g in plan_by_id[ogr.id]["gruplar"]}
        if await ders_hakki.kullanilabilir_telafi(session, ogr.id) <= 0:
            continue
        for s in gelecek:
            if s.grup_id in o_gruplari or s.durum != OturumDurum.planli or s.tarih < bugun:
                continue
            session.add(TelafiPlani(oturum_id=s.id, ogrenci_id=ogr.id, olusturan_id=None))
            await session.flush()
            telafi_sayisi += 1
            break

    # ---------- özet ----------
    bakiyeler = await ders_hakki.bakiyeler(session, [o.id for o, _ in ogrenciler])
    n_resit_uyari = sum(1 for _, d in ogrenciler if d.get("uyari"))
    sayilar = {
        "Antrenör": len(antrenorler),
        "Grup": len(gruplar),
        "Öğrenci": len(ogrenciler),
        "  pasif öğrenci": sum(1 for o, _ in ogrenciler if o.durum == OgrenciDurum.pasif),
        "  reşit uyarısı (birincil iletişim hâlâ veli)": n_resit_uyari,
        "Veli hesabı": veli_hesap_sayisi,
        "Öğrenci hesabı": sum(1 for o, _ in ogrenciler if o.kullanici_id),
        "Ders oturumu": len(oturumlar),
        "  geçmiş / gelecek": f"{len(gecmis)} / {len(gelecek)} (iptal: {len(iptaller)})",
        "Yoklama kaydı": yoklama_sayisi,
        "  işlenen devamsızlık (telafi hakkı doğan)": devamsizlik_islenen,
        "Planlanmış telafi dersi": telafi_sayisi,
        "Telafi bakiyesi olan öğrenci": sum(1 for b in bakiyeler.values() if b["telafi"] > 0),
        "Normal bakiyesi 0 olan öğrenci": sum(1 for o, _ in aktifler if bakiyeler[o.id]["normal"] == 0),
    }
    antrenor_giris = ("Antrenör (" + ANTRENORLER[0][0] + ")", ANTRENORLER[0][1])
    girisler = [antrenor_giris, veli_ornek, resit_ornek]
    return {"sayilar": sayilar, "girisler": [g for g in girisler if g]}


def _grup_antrenor(gruplar: dict[str, Grup], grup_id: uuid.UUID) -> uuid.UUID:
    return next(g.antrenor_id for g in gruplar.values() if g.id == grup_id)


def gruplar_antrenor(gruplar: dict[str, Grup], oturum: DersOturumu) -> uuid.UUID:
    return _grup_antrenor(gruplar, oturum.grup_id)


# --- Ödeme örnek verisi (ayrı komut: ornek-odeme-verisi) ---

ODEME_OGRENCI_SAYISI = 30
BEKLEYEN_SIRALAR = {1, 5, 9, 13, 17, 21}
OZEL_FIYAT_SIRALARI = {0, 9, 18, 27}
IPTAL_EDILENLER = {(3, 1): "Yanlış tutar girildi", (7, 2): "Veli ödemeyi geri istedi"}  # (sıra, kaç ay önce)
YONTEMLER = [OdemeYontemi.nakit, OdemeYontemi.havale_eft, OdemeYontemi.nakit, OdemeYontemi.havale_eft,
             OdemeYontemi.nakit, OdemeYontemi.nakit, OdemeYontemi.diger]


def _ay_basi(bugun: date, geri: int) -> date:
    toplam = bugun.year * 12 + bugun.month - 1 - geri
    yil, ay = divmod(toplam, 12)
    return date(yil, ay + 1, 1)


async def yukle_odeme() -> int:
    """Örnek öğrencilere son 3 ay + geçerli ay için paket ve ödeme ekler (yalnızca ENV=dev).

    SINIR: Geçmiş aylar için defterde `paket_yuklemesi` YAZILMAZ; örnek ders hakkı bakiyeleri zaten
    `ornek-veri` ile defterde vardır, çift yükleme olmasın diye. Bu yüzden 'odendi' paketlerin çoğunun
    defterde yüklemesi yoktur (gerçek akışta ödeme alınca ders yüklenir)."""
    from app.api.paketler import ay_ekle

    if settings.env not in ("dev", "demo"):
        print(f"ornek-odeme-verisi yalnızca ENV=dev veya ENV=demo iken çalışır (şu an ENV={settings.env}).")
        return 1
    bugun = bugun_fn()
    async with SessionLocal() as session:
        if not await _zaten_yuklu(session):
            print("Önce `ornek-veri` komutunu çalıştırın (örnek öğrenciler yok).")
            return 1
        ogrenciler = list(
            (
                await session.execute(
                    select(Ogrenci)
                    .where(Ogrenci.sentetik.is_(False), Ogrenci.durum == OgrenciDurum.aktif)
                    .order_by(Ogrenci.kayit_tarihi, Ogrenci.id)
                    .limit(ODEME_OGRENCI_SAYISI)
                )
            ).scalars()
        )
        if not ogrenciler:
            print("Örnek öğrenci bulunamadı.")
            return 1
        var = (
            await session.execute(
                select(OgrenciPaketi.id).where(OgrenciPaketi.ogrenci_id.in_([o.id for o in ogrenciler])).limit(1)
            )
        ).first()
        if var is not None:
            print("Ödeme örnek verisi zaten yüklü (örnek öğrencilerin paketi var). Hiçbir şey eklenmedi.")
            return 0

        paket = (
            await session.execute(select(Paket).where(Paket.ad == "Aylık 8 Ders").order_by(Paket.olusturma).limit(1))
        ).scalar_one_or_none()
        if paket is None:
            paket = Paket(
                ad="Aylık 8 Ders", tur=PaketTuru.aylik, ders_sayisi=8, sure_ay=1, varsayilan_fiyat=Decimal("3400.00"),
                aktif=True,
            )
            session.add(paket)
            await session.flush()
        yonetici = (
            await session.execute(select(Kullanici).where(Kullanici.rol == Rol.admin).order_by(Kullanici.olusturma).limit(1))
        ).scalar_one_or_none()
        yonetici_id = yonetici.id if yonetici else None

        sayac = {"paket": 0, "odeme": 0, "iptal": 0, "bekleyen": 0, "ozel": 0}
        for sira, ogr in enumerate(ogrenciler):
            ozel = sira in OZEL_FIYAT_SIRALARI
            fiyat = Decimal("2900.00") if ozel else paket.varsayilan_fiyat
            for geri in (3, 2, 1, 0):
                if geri and (sira + geri) % 7 == 0:
                    continue  # her ay herkes paket almaz
                baslangic = min(_ay_basi(bugun, geri) + timedelta(days=(sira * 3) % 20), bugun)
                bekleyen = geri == 0 and sira in BEKLEYEN_SIRALAR
                iptal_nedeni = IPTAL_EDILENLER.get((sira, geri))
                durum = OgrenciPaketiDurum.odeme_bekliyor if (bekleyen or iptal_nedeni) else OgrenciPaketiDurum.odendi
                atama_zamani = _kulup_zamani(baslangic, time(10, 0))
                op = OgrenciPaketi(
                    ogrenci_id=ogr.id, paket_id=paket.id, ders_sayisi=paket.ders_sayisi,
                    liste_fiyati=paket.varsayilan_fiyat, uygulanan_fiyat=fiyat, fiyat_ozel_mi=ozel,
                    fiyat_degistiren_id=yonetici_id if ozel else None, baslangic=baslangic,
                    bitis=ay_ekle(baslangic, paket.sure_ay), durum=durum, olusturan_id=yonetici_id,
                    olusturma=atama_zamani,
                )
                session.add(op)
                await session.flush()
                sayac["paket"] += 1
                sayac["ozel"] += 1 if ozel else 0
                if bekleyen:
                    sayac["bekleyen"] += 1
                    continue
                odeme_tarihi = min(baslangic + timedelta(days=sira % 4), bugun)
                odeme = Odeme(
                    ogrenci_paketi_id=op.id, tutar=fiyat, tarih=odeme_tarihi,
                    yontem=YONTEMLER[(sira + geri) % len(YONTEMLER)], olusturan_id=yonetici_id,
                    aciklama="Örnek veri" if sira % 5 == 0 else None,
                    olusturma=_kulup_zamani(odeme_tarihi, time(11, 30)),
                )
                if iptal_nedeni:
                    odeme.iptal_zamani = _kulup_zamani(odeme_tarihi, time(15, 0))
                    odeme.iptal_nedeni = iptal_nedeni
                    odeme.iptal_eden_id = yonetici_id
                    sayac["iptal"] += 1
                session.add(odeme)
                sayac["odeme"] += 1
        await session.commit()

    print("Ödeme örnek verisi yüklendi.")
    print(f"  Öğrenci: {len(ogrenciler)}")
    print(f"  Öğrenci paketi: {sayac['paket']} (özel fiyatlı: {sayac['ozel']})")
    print(f"  Ödeme: {sayac['odeme']} (iptal edilmiş: {sayac['iptal']})")
    print(f"  Geçerli ayda ödeme bekleyen paket: {sayac['bekleyen']}")
    print("  NOT: Geçmiş paketler için defterde ders yüklemesi (paket_yuklemesi) YAZILMADI; örnek ders hakkı")
    print("  verisi zaten defterde olduğundan çift yükleme olmasın diye. Bu verideki ödenmiş paketlerin")
    print("  çoğunda defter karşılığı yoktur (yalnızca örnek veri sınırı).")
    return 0
