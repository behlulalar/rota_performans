"""WhatsApp gönderimi ve ban koruması. Evolution API httpx.MockTransport ile taklit edilir (gerçek ağ yok);
saat ve rastgele aralık enjekte edilir, Redis test veritabanıdır."""
import json
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select, update

from app import bildirim as bsvc
from app import whatsapp as wa
from app import whatsapp_gonder as wag
from app.config import settings
from app.db import SessionLocal
from app.models import (
    Bildirim,
    BildirimDurum,
    BildirimKanal,
    BildirimTercihi,
    DenetimKaydi,
    DersOturumu,
    Duyuru,
    DuyuruHedefTuru,
    IletisimKisisi,
    KulupAyari,
    PushAbonelik,
    YoklamaDurum,
)
from tests.test_bildirim import T0, isaretle, ortam, oturum
from tests.test_duyuru import TUM, bildirimler, gonder, ogrenci, veli_hesabi
from tests.test_yoklama import yonetici  # noqa: F401  (fixture)

# 2026-11-03 09:00 UTC = 12:00 İstanbul. T0 (2 Kasım 18:00 UTC) + 3 dk planlı satırlar 15 saat eski, yani bayat değil.
S = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
SABIT = lambda alt, ust: alt  # noqa: E731  (rastgele kaynağı: hep alt sınır)


class SahteEvolution:
    """Bağlı bir Evolution: fetchInstances + sendText. `gonder_modu` ile gönderim sonucu seçilir."""

    def __init__(self):
        self.durum = "open"
        self.gonder_modu = "ok"  # ok | baglanti | zaman_asimi | 500 | 401 | 400
        self.gonderilen: list[dict] = []
        self.istekler: list[str] = []

    def __call__(self, r: httpx.Request) -> httpx.Response:
        yol = r.url.path
        self.istekler.append(f"{r.method} {yol}")
        if yol == "/instance/fetchInstances":
            jid = "905321234567@s.whatsapp.net" if self.durum == "open" else None
            return httpx.Response(200, json=[{"name": "rota", "connectionStatus": self.durum, "ownerJid": jid, "profileName": "Rota"}])
        if yol == "/message/sendText/rota":
            self.gonderilen.append(json.loads(r.content))
            if self.gonder_modu == "baglanti":
                raise httpx.ConnectError("kapalı")
            if self.gonder_modu == "zaman_asimi":
                raise httpx.ReadTimeout("yanıt yok")
            if self.gonder_modu != "ok":
                return httpx.Response(int(self.gonder_modu), json={})
            return httpx.Response(201, json={"key": {"id": "X"}})
        return httpx.Response(404, json={})

    @property
    def gonderim_sayisi(self) -> int:
        return len(self.gonderilen)


@pytest.fixture
def evolution(monkeypatch):
    sahte = SahteEvolution()
    monkeypatch.setattr(settings, "evolution_url", "http://evolution:8080")
    monkeypatch.setattr(settings, "evolution_api_key", "gizli")
    monkeypatch.setattr(settings, "evolution_instance", "rota")
    monkeypatch.setattr(
        wa, "_istemci",
        lambda: httpx.AsyncClient(base_url="http://evolution:8080", headers={"apikey": "gizli"}, transport=httpx.MockTransport(sahte)),
    )
    return sahte


async def calistir(simdi=S, rastgele=SABIT):
    async with SessionLocal() as s:
        return await wag.whatsapp_gonder(s, simdi, rastgele=rastgele)


async def kur(ad="Deniz", **kw):
    """Gelmedi işaretli öğrenci: whatsapp + push satırı. (ogrenci_id, kullanici_id, kisi_id)."""
    o, k, kisi = await ortam(ad=ad, **kw)
    async with SessionLocal() as s:
        gun = (await s.execute(select(func.count()).select_from(DersOturumu))).scalar_one()  # her çağrıya ayrı ders günü
    await isaretle(o, await oturum(gun), YoklamaDurum.gelmedi)
    return o, k, kisi


async def satir(kanal=BildirimKanal.whatsapp, ogrenci_id=None):
    async with SessionLocal() as s:
        q = select(Bildirim).where(Bildirim.kanal == kanal).order_by(Bildirim.id)
        if ogrenci_id:
            q = q.where(Bildirim.ogrenci_id == ogrenci_id)
        return (await s.execute(q)).scalars().all()


async def tek(kanal=BildirimKanal.whatsapp):
    (b,) = await satir(kanal)
    return b


async def ayar_yaz(**degerler):
    async with SessionLocal() as s:
        a = await s.get(KulupAyari, 1)
        if a is None:
            a = KulupAyari(id=1)
            s.add(a)
        for k, v in degerler.items():
            setattr(a, k, v)
        await s.commit()


async def gecmis_gonderim(ogrenci_id, kisi_id, zaman, adet=1):
    """Daha önce başarıyla gönderilmiş WhatsApp satırları (limit ve ısınma sayımı için)."""
    async with SessionLocal() as s:
        for _ in range(adet):
            s.add(Bildirim(
                ogrenci_id=ogrenci_id, alici_iletisim_id=kisi_id, kanal=BildirimKanal.whatsapp, sablon="ders_gelmedi",
                durum=BildirimDurum.gonderildi, planli_zaman=zaman, gonderim_zamani=zaman,
            ))
        await s.commit()


async def redis_al():
    return Redis.from_url(settings.redis_url, decode_responses=True)


# ---------- temel gönderim ----------


async def test_basarili_gonderim_govde_ve_metin(evolution):
    await kur()
    sonuc = await calistir()
    assert sonuc["gonderildi"] == 1
    (govde,) = evolution.gonderilen
    assert govde["number"] == "905551112233" and govde["delay"] == wag.YAZIYOR_MS[0]
    assert "Deniz" in govde["text"] and "Rota Performans Akademi" in govde["text"] and "02.11.2026 17:00" in govde["text"]
    assert "5551112233" not in govde["text"] and "http" not in govde["text"]
    b = await tek()
    assert b.durum == BildirimDurum.gonderildi and b.gonderim_zamani == S and b.hata is None
    # Tekrar çalışınca aynı mesaj bir daha gitmez.
    await calistir(S + timedelta(minutes=5))
    assert evolution.gonderim_sayisi == 1


async def test_yapilandirilmamisken_dokunulmaz(monkeypatch):
    monkeypatch.setattr(settings, "evolution_url", "")
    await kur()
    assert not any((await calistir()).values())
    b = await tek()
    assert b.durum == BildirimDurum.bekliyor and b.hata is None and b.deneme == 0


async def test_planli_zaman_gelmemisse_bekler(evolution):
    await kur()
    await calistir(T0)  # planlı zaman T0 + 3 dk
    assert evolution.gonderim_sayisi == 0 and evolution.istekler == []
    assert (await tek()).durum == BildirimDurum.bekliyor


async def test_bagli_degilken_satirlara_dokunulmaz(evolution):
    await kur()
    for durum in ("close", "connecting"):
        evolution.durum = durum
        assert not any((await calistir(S + timedelta(minutes=5))).values())
    b = await tek()
    assert b.durum == BildirimDurum.bekliyor and b.deneme == 0 and b.hata is None and evolution.gonderim_sayisi == 0


async def test_baglanti_kopmasi_devre_kesiciyi_acar_ve_baglaninca_sure_dolunca_kapanir(evolution):
    await kur()
    evolution.durum = "close"
    await calistir()
    r = await redis_al()
    try:
        acik, sebep = await wag.devre_durumu(r, S)
        assert acik and sebep == "bağlantı koptu"
    finally:
        await r.aclose()
    # Bağlandı ama 30 dk dolmadı: gönderilmez. Süre dolunca kapanır ve gönderir.
    evolution.durum = "open"
    await calistir(S + timedelta(minutes=29))
    assert evolution.gonderim_sayisi == 0
    assert (await calistir(S + timedelta(minutes=31)))["gonderildi"] == 1
    r = await redis_al()
    try:
        assert await wag.devre_durumu(r, S + timedelta(minutes=31)) == (False, None)
        assert await r.exists(wag.DEVRE_ANAHTAR) == 0
    finally:
        await r.aclose()


# ---------- pencere, aralık, limitler ----------


async def test_gonderim_penceresi_disinda_bekler(evolution):
    await kur()
    # 18:00 UTC = 21:00 İstanbul (bitiş saati dahil değil), 05:00 UTC = 08:00.
    for an in (datetime(2026, 11, 3, 18, 0, tzinfo=timezone.utc), datetime(2026, 11, 3, 5, 0, tzinfo=timezone.utc)):
        await calistir(an)
    assert evolution.gonderim_sayisi == 0
    assert (await tek()).durum == BildirimDurum.bekliyor
    # 17:59 UTC = 20:59: pencere içi.
    assert (await calistir(datetime(2026, 11, 3, 17, 59, tzinfo=timezone.utc)))["gonderildi"] == 1


async def test_pencere_ayardan_okunur(evolution):
    await kur()
    await ayar_yaz(wa_baslangic_saat=13, wa_bitis_saat=18)
    await calistir(S)  # 12:00
    assert evolution.gonderim_sayisi == 0
    assert (await calistir(S + timedelta(hours=1)))["gonderildi"] == 1  # 13:00


async def test_dongude_en_fazla_bir_mesaj_ve_aralik_dolmadan_ikinci_gitmez(evolution):
    await kur("Ada")
    await kur("Ela")
    assert (await calistir(S))["gonderildi"] == 1
    assert evolution.gonderim_sayisi == 1
    await calistir(S + timedelta(seconds=10))
    await calistir(S + timedelta(seconds=wag.ARALIK_SN[0] - 1))
    assert evolution.gonderim_sayisi == 1
    assert (await calistir(S + timedelta(seconds=wag.ARALIK_SN[0])))["gonderildi"] == 1
    assert evolution.gonderim_sayisi == 2


async def test_aralik_rastgele_25_70_ve_her_gonderimden_sonra_yenilenir(evolution):
    await kur("Ada")
    await calistir(S, rastgele=lambda alt, ust: alt if (alt, ust) != wag.ARALIK_SN else ust)
    r = await redis_al()
    try:
        assert float(await r.get(wag.SONRAKI_ANAHTAR)) == S.timestamp() + 70
    finally:
        await r.aclose()
    # Varsayılan rastgele kaynağı: aralık 25–70 sn içinde.
    await kur("Ela")
    await calistir(S + timedelta(seconds=71), rastgele=__import__("random").randint)
    r = await redis_al()
    try:
        fark = float(await r.get(wag.SONRAKI_ANAHTAR)) - (S + timedelta(seconds=71)).timestamp()
        assert 25 <= fark <= 70
    finally:
        await r.aclose()


async def test_saatlik_limit(evolution):
    await ayar_yaz(wa_saatlik_limit=2)
    for ad in ("Ada", "Ela", "Can"):
        await kur(ad)
    assert (await calistir(S))["gonderildi"] == 1
    assert (await calistir(S + timedelta(minutes=2)))["gonderildi"] == 1
    assert (await calistir(S + timedelta(minutes=4)))["gonderildi"] == 0  # saatte 2
    assert evolution.gonderim_sayisi == 2
    assert (await calistir(S + timedelta(minutes=61)))["gonderildi"] == 1  # ilk gönderim saatin dışına çıktı


async def test_gunluk_limit_ayardan(evolution):
    o, _, kisi = await kur("Ada")
    await kur("Ela")
    await gecmis_gonderim(o, kisi, S - timedelta(days=40))  # ısınma bitmiş numara
    await gecmis_gonderim(o, kisi, S - timedelta(hours=5), adet=2)
    await ayar_yaz(wa_gunluk_limit=2)
    await calistir(S)
    assert evolution.gonderim_sayisi == 0
    await ayar_yaz(wa_gunluk_limit=3)
    assert (await calistir(S))["gonderildi"] == 1


async def test_gunluk_sayim_istanbul_gunune_gore(evolution):
    o, _, kisi = await kur("Ada")
    await gecmis_gonderim(o, kisi, S - timedelta(days=40))
    # İstanbul günü 00:00 = önceki gün 21:00 UTC. 2 Kasım 20:59 UTC (= 23:59 İstanbul, dün) bugünkü sayıma girmez.
    await ayar_yaz(wa_gunluk_limit=1)
    await gecmis_gonderim(o, kisi, datetime(2026, 11, 2, 20, 59, tzinfo=timezone.utc))
    assert (await calistir(S))["gonderildi"] == 1


def test_isinma_takvimi():
    beklenen = {1: 20, 2: 20, 3: 20, 4: 50, 7: 50, 8: 120, 14: 120, 15: None, 60: None}
    for gun, limit in beklenen.items():
        assert wag.isinma_limiti(gun) == limit, gun


async def test_isinma_limiti_gunluk_ayari_ezer(evolution):
    # İlk gönderim bugün (gün 1): günlük 20 ayardaki 250'den önce gelir.
    o, _, kisi = await kur("Ada")
    await gecmis_gonderim(o, kisi, S - timedelta(hours=3), adet=20)
    await ayar_yaz(wa_saatlik_limit=200)
    await calistir(S)
    assert evolution.gonderim_sayisi == 0
    # İlk gönderim 5 gün önce (gün 6): sınır 50.
    await gecmis_gonderim(o, kisi, S - timedelta(days=5))
    assert (await calistir(S))["gonderildi"] == 1


async def test_isinma_ayar_isinmadan_dusukse_ayar_gecerli(evolution):
    o, _, kisi = await kur("Ada")
    await gecmis_gonderim(o, kisi, S - timedelta(days=6))  # gün 7: ısınma 50
    await gecmis_gonderim(o, kisi, S - timedelta(hours=3), adet=10)
    await ayar_yaz(wa_gunluk_limit=10)
    await calistir(S)
    assert evolution.gonderim_sayisi == 0


# ---------- öncelik ----------


async def duyuru_satiri(ad, *, kanal_push=False, her_iki=False, planli=None, kanal=BildirimKanal.whatsapp, durum=BildirimDurum.bekliyor,
                        duyuru=None, kullanici_id=None, metin="Yarın antrenman yok."):
    o = await ogrenci(ad, kullanici_id=kullanici_id)
    async with SessionLocal() as s:
        kisi = (await s.execute(select(IletisimKisisi).where(IletisimKisisi.ogrenci_id == o.id))).scalar_one()
        d = duyuru
        if d is None:
            d = Duyuru(baslik="Duyuru", metin=metin, hedef_tur=DuyuruHedefTuru.tum, hedef={}, kanal_push=kanal_push,
                       kanal_whatsapp=True, her_iki_kanal=her_iki)
            s.add(d)
            await s.flush()
        s.add(Bildirim(
            ogrenci_id=o.id, alici_iletisim_id=kisi.id, kanal=kanal, sablon="duyuru", parametreler={"duyuru_id": str(d.id)},
            duyuru_id=d.id, durum=durum, planli_zaman=planli or (S - timedelta(hours=20)),
        ))
        await s.commit()
        return o.id, kisi.id, d


async def test_kisisel_bildirim_duyurudan_once_gider(evolution):
    # Duyuru daha eski planlı olsa da kişisel (devamsızlık) önce gider.
    await duyuru_satiri("Zeynep", planli=S - timedelta(hours=20), metin="Bayram tatili duyurusu")
    await kur("Deniz")
    await calistir(S)
    assert "Deniz" in evolution.gonderilen[0]["text"]
    await calistir(S + timedelta(seconds=30))
    assert evolution.gonderilen[1]["text"] == "Bayram tatili duyurusu"  # duyuru metni olduğu gibi


# ---------- push varsa atla ----------


async def abonelik_ekle(kullanici_id, son_kullanim):
    async with SessionLocal() as s:
        s.add(PushAbonelik(kullanici_id=kullanici_id, endpoint=f"https://push.test/{kullanici_id}", p256dh="p" * 20,
                           auth="a" * 10, son_kullanim=son_kullanim))
        await s.commit()


async def test_push_ile_ulasan_aliciya_whatsapp_gitmez(evolution):
    _, k, _ = await kur()
    await abonelik_ekle(k, S - timedelta(days=1))
    sonuc = await calistir()
    assert sonuc["iptal"] == 1 and evolution.gonderim_sayisi == 0
    b = await tek()
    assert b.durum == BildirimDurum.iptal and b.hata == "push ile ulaşıyor"


async def test_push_kurali_istisnalari(evolution):
    # Cihaz hiç başarılı push almadı (son_kullanim boş) -> gönderilir.
    _, k, _ = await kur("Ada")
    await abonelik_ekle(k, None)
    assert (await calistir(S))["gonderildi"] == 1
    # Son kullanım 30 günden eski -> gönderilir.
    _, k, _ = await kur("Ela")
    await abonelik_ekle(k, S - timedelta(days=31))
    assert (await calistir(S + timedelta(minutes=1)))["gonderildi"] == 1
    # Hesabı olmayan alıcı -> gönderilir.
    await kur("Can", hesap=False)
    assert (await calistir(S + timedelta(minutes=2)))["gonderildi"] == 1


async def test_push_varsa_atla_ayari_kapaliysa_gonderilir(evolution):
    _, k, _ = await kur()
    await abonelik_ekle(k, S - timedelta(days=1))
    await ayar_yaz(wa_push_varsa_atla=False)
    assert (await calistir())["gonderildi"] == 1


async def test_push_satiri_yoksa_ya_da_basarisizsa_whatsapp_gider(evolution):
    # Veli push'u kapattı (push satırı hiç oluşmadı) ama eski bir cihazı var: WhatsApp yine gider.
    o, k, _ = await ortam(ad="Ada")
    async with SessionLocal() as s:
        s.add(BildirimTercihi(kullanici_id=k, push=False))
        await s.commit()
    await abonelik_ekle(k, S - timedelta(days=1))
    await isaretle(o, await oturum(), YoklamaDurum.gelmedi)
    assert (await satir(BildirimKanal.push)) == []
    assert (await calistir())["gonderildi"] == 1
    # Push satırı hatalı bittiyse de gider.
    _, k2, _ = await kur("Ela")
    await abonelik_ekle(k2, S - timedelta(days=1))
    async with SessionLocal() as s:
        await s.execute(update(Bildirim).where(Bildirim.kanal == BildirimKanal.push, Bildirim.alici_iletisim_id != None).values(durum=BildirimDurum.hata))  # noqa: E711
        await s.commit()
    assert (await calistir(S + timedelta(minutes=1)))["gonderildi"] == 1


async def push_kardesi(kisi_id, o_id, d, kullanici_id):
    async with SessionLocal() as s:
        s.add(Bildirim(
            ogrenci_id=o_id, alici_iletisim_id=kisi_id, kanal=BildirimKanal.push, sablon="duyuru",
            parametreler={"duyuru_id": str(d.id)}, duyuru_id=d.id, durum=BildirimDurum.gonderildi, planli_zaman=S - timedelta(hours=20),
        ))
        await s.commit()


async def test_duyuruda_her_iki_kanal_istisnasi(evolution):
    # her_iki_kanal kapalı: push ile ulaşılan alıcıya WhatsApp gitmez.
    k1 = await veli_hesabi("a@v.com", cihaz=False)
    await abonelik_ekle(k1, S - timedelta(days=1))
    o1, kisi1, d1 = await duyuru_satiri("Ada", kanal_push=True, her_iki=False, kullanici_id=k1)
    await push_kardesi(kisi1, o1, d1, k1)
    await calistir(S)
    assert evolution.gonderim_sayisi == 0
    b = (await satir(ogrenci_id=o1))[0]
    assert b.durum == BildirimDurum.iptal and b.hata == "push ile ulaşıyor"
    # her_iki_kanal açık: aynı durumda gönderilir.
    k2 = await veli_hesabi("b@v.com", cihaz=False)
    await abonelik_ekle(k2, S - timedelta(days=1))
    o2, kisi2, d2 = await duyuru_satiri("Ela", kanal_push=True, her_iki=True, kullanici_id=k2)
    await push_kardesi(kisi2, o2, d2, k2)
    assert (await calistir(S + timedelta(minutes=1)))["gonderildi"] == 1
    # Duyuru yalnız WhatsApp kanalındaysa (push gitmiyor) kural işlemez.
    k3 = await veli_hesabi("c@v.com", cihaz=False)
    await abonelik_ekle(k3, S - timedelta(days=1))
    await duyuru_satiri("Can", kanal_push=False, her_iki=False, kullanici_id=k3)
    assert (await calistir(S + timedelta(minutes=2)))["gonderildi"] == 1


# ---------- hata, yeniden deneme, devre kesici, belirsiz sonuç ----------


async def test_kesin_ag_hatasi_geri_cekilmeyle_yeniden_denenir(evolution):
    await kur()
    evolution.gonder_modu = "baglanti"
    an = S
    for deneme in range(1, wag.MAKS_DENEME):
        await calistir(an)
        r = await redis_al()  # tek satır art arda hata verdiği için devre kesici açılır; bu test onu ayrı tutar
        await r.delete(wag.DEVRE_ANAHTAR, wag.HATA_SAYACI_ANAHTAR)
        await r.aclose()
        b = await tek()
        assert b.durum == BildirimDurum.bekliyor and b.deneme == deneme and b.gonderim_zamani is None
        assert b.planli_zaman == an + timedelta(minutes=2**deneme) and b.hata == "WhatsApp servisi hatası"
        an = b.planli_zaman
    await calistir(an)
    b = await tek()
    assert b.durum == BildirimDurum.hata and b.deneme == wag.MAKS_DENEME and b.hata == "WhatsApp servisi hatası"
    # Kişisel veri hata alanına yazılmadı.
    assert "5551112233" not in (b.hata or "") and "Deniz" not in (b.hata or "")


async def test_hata_sonrasi_basari_gonderir(evolution):
    await ayar_yaz(wa_saatlik_limit=200)
    await kur()
    evolution.gonder_modu = "baglanti"
    await calistir(S)
    evolution.gonder_modu = "ok"
    b = await tek()
    assert (await calistir(b.planli_zaman))["gonderildi"] == 1
    assert (await tek()).durum == BildirimDurum.gonderildi


async def test_devre_kesici_art_arda_uc_hatada_acilir_ve_sure_dolunca_kapanir(evolution):
    for ad in ("Ada", "Ela", "Can", "Eda"):
        await kur(ad)
    evolution.gonder_modu = "baglanti"
    for i in range(3):
        await calistir(S + timedelta(seconds=30 * i))
    assert evolution.gonderim_sayisi == 3
    r = await redis_al()
    try:
        assert await wag.devre_durumu(r, S + timedelta(minutes=2)) == (True, "WhatsApp servisi hatası")
        assert 0 < await r.ttl(wag.DEVRE_ANAHTAR) <= 30 * 60
    finally:
        await r.aclose()
    # Devre açıkken Evolution düzelse bile gönderim yapılmaz.
    evolution.gonder_modu = "ok"
    await calistir(S + timedelta(minutes=10))
    assert evolution.gonderim_sayisi == 3
    # 30 dk sonra (bağlantı sağlam) kapanır ve gönderim sürer.
    assert (await calistir(S + timedelta(minutes=31)))["gonderildi"] == 1
    r = await redis_al()
    try:
        assert await wag.devre_durumu(r, S + timedelta(minutes=31)) == (False, None)
    finally:
        await r.aclose()


async def test_basari_art_arda_hata_sayacini_sifirlar(evolution):
    for ad in ("Ada", "Ela", "Can", "Eda", "Fil"):
        await kur(ad)
    sira = [("baglanti", 2), ("ok", 1), ("baglanti", 2)]
    i = 0
    for mod, adet in sira:
        evolution.gonder_modu = mod
        for _ in range(adet):
            await calistir(S + timedelta(seconds=30 * i))
            i += 1
    r = await redis_al()
    try:
        assert (await wag.devre_durumu(r, S + timedelta(minutes=5)))[0] is False
    finally:
        await r.aclose()


async def test_belirsiz_sonuc_yeniden_denenmez(evolution):
    await ayar_yaz(wa_saatlik_limit=200)
    await kur()
    evolution.gonder_modu = "zaman_asimi"
    sonuc = await calistir(S)
    assert sonuc["hata"] == 1 and sonuc["yeniden"] == 0
    b = await tek()
    assert b.durum == BildirimDurum.hata and b.hata == wag.BELIRSIZ_HATA and b.deneme == 0
    evolution.gonder_modu = "ok"
    for dk in (1, 5, 60, 600):
        await calistir(S + timedelta(minutes=dk))
    assert evolution.gonderim_sayisi == 1  # ikinci mesaj yok
    assert (await tek()).durum == BildirimDurum.hata


async def test_sunucu_hatasi_5xx_belirsiz_sayilir(evolution):
    await kur()
    evolution.gonder_modu = "500"
    await calistir(S)
    b = await tek()
    assert b.durum == BildirimDurum.hata and b.hata == wag.BELIRSIZ_HATA
    evolution.gonder_modu = "ok"
    await calistir(S + timedelta(minutes=5))
    assert evolution.gonderim_sayisi == 1


async def test_reddedilen_istek_kesin_hata_ve_gecersiz_numara_kalici(evolution):
    await kur("Ada")
    evolution.gonder_modu = "401"
    await calistir(S)
    b = await tek()
    assert b.durum == BildirimDurum.bekliyor and b.deneme == 1  # kesin: yeniden denenir
    await kur("Ela")
    evolution.gonder_modu = "400"  # numara WhatsApp'ta yok
    await calistir(S + timedelta(minutes=1))
    b = (await satir())[1]
    assert b.durum == BildirimDurum.hata and b.hata == "numara WhatsApp'ta yok" and b.gonderim_zamani is None


async def test_gonderim_sirasinda_beklenmeyen_cokme_mesaji_tekrar_gondermez(evolution, monkeypatch):
    await kur()

    async def coker(*a, **k):
        raise RuntimeError("beklenmeyen")

    monkeypatch.setattr(wa, "metin_gonder", coker)
    await calistir(S)
    b = await tek()
    assert b.durum == BildirimDurum.hata and b.hata == wag.BELIRSIZ_HATA
    assert (await calistir(S + timedelta(minutes=5)))["gonderildi"] == 0


async def test_belirsiz_gonderim_limite_sayilir(evolution):
    await ayar_yaz(wa_saatlik_limit=1)
    await kur("Ada")
    await kur("Ela")
    evolution.gonder_modu = "zaman_asimi"
    await calistir(S)
    evolution.gonder_modu = "ok"
    await calistir(S + timedelta(minutes=2))  # belirsiz mesaj da saatlik hakkı tüketti
    assert evolution.gonderim_sayisi == 1


async def test_24_saatten_eski_bekleyen_iptal_edilir(evolution):
    await kur()
    b0 = await tek()
    sonuc = await calistir(b0.planli_zaman + timedelta(hours=24, minutes=1))
    assert sonuc["iptal"] == 1 and evolution.gonderim_sayisi == 0
    b = await tek()
    assert b.durum == BildirimDurum.iptal and b.hata == "süresi geçti"


# ---------- söyleniş ----------


def test_soylenisler_ucer_tane_imzali_linksiz():
    for sablon, secenekler in bsvc.SOYLENISLER.items():
        assert sablon in bsvc.TERCIH_TURU and len(secenekler) == 3 and len(set(secenekler)) == 3
        for m in secenekler:
            assert "Rota Performans Akademi" in m and "{ad}" in m and "http" not in m and "www" not in m
            dolu = m.format(ad="Deniz", tarih="02.11.2026", saat="17:00", bakiye=2)
            assert "{" not in dolu and "Deniz" in dolu
        # Seçim kimliğe göre deterministik ve üç söylenişi de döndürür.
        assert [bsvc.soylenis_sec(sablon, i) for i in range(3)] == secenekler
        assert bsvc.soylenis_sec(sablon, 7) == bsvc.soylenis_sec(sablon, 1) == bsvc.soylenis_sec(sablon, 7)


async def test_metin_soylenisi_id_mod_3_ve_telefon_icermez(evolution):
    # Üç farklı bildirim kimliği üç farklı söylenişi kullanır.
    metinler = {}
    for ad in ("Ada", "Ela", "Can"):
        await kur(ad)
    async with SessionLocal() as s:
        for b in (await s.execute(select(Bildirim).where(Bildirim.kanal == BildirimKanal.whatsapp).order_by(Bildirim.id))).scalars():
            m = await bsvc.metin_olustur(s, b, soylenis=True)
            beklenen = bsvc.soylenis_sec(b.sablon, b.id)
            assert m.startswith(beklenen.split("{ad}")[0].replace("  ", " "))
            assert m == await bsvc.metin_olustur(s, b, soylenis=True)  # deterministik
            assert "5551112233" not in m and "+90" not in m and "http" not in m
            metinler[b.id % 3] = m
    assert len(metinler) == 3
    # soylenis=False eski davranış (push / panel metni) değişmedi.
    async with SessionLocal() as s:
        b = (await s.execute(select(Bildirim).where(Bildirim.kanal == BildirimKanal.push).order_by(Bildirim.id))).scalars().first()
        assert await bsvc.metin_olustur(s, b) == bsvc.SABLONLAR["ders_gelmedi"].format(
            ad="Ada", tarih="02.11.2026", saat="17:00", bakiye=0
        ).replace("  ", " ")


async def test_gunluge_kisisel_veri_yazilmaz(evolution, caplog):
    await kur()
    with caplog.at_level("DEBUG"):
        await calistir()
    tum = caplog.text
    assert "5551112233" not in tum and "Deniz" not in tum


# ---------- metin_gonder (Evolution istemcisi) ----------


async def test_metin_gonder_istegi_ve_hata_siniflandirmasi(evolution):
    await wa.metin_gonder("+905551112233", "Merhaba", 2000)
    assert evolution.gonderilen[-1] == {"number": "905551112233", "text": "Merhaba", "delay": 2000}
    evolution.gonder_modu = "baglanti"
    with pytest.raises(wa.KesinHata):
        await wa.metin_gonder("905551112233", "x", 0)
    evolution.gonder_modu = "zaman_asimi"
    with pytest.raises(wa.BelirsizSonuc):
        await wa.metin_gonder("905551112233", "x", 0)
    evolution.gonder_modu = "500"
    with pytest.raises(wa.BelirsizSonuc):
        await wa.metin_gonder("905551112233", "x", 0)
    evolution.gonder_modu = "400"
    with pytest.raises(wa.GecersizNumara):
        await wa.metin_gonder("905551112233", "x", 0)
    with pytest.raises(wa.GecersizNumara):
        await wa.metin_gonder("abc", "x", 0)


# ---------- ayar API ----------

AYAR = "/api/ayarlar"


async def test_ayar_dogrulamalari_422(istemci, yonetici):
    for govde in (
        {"wa_saatlik_limit": 0}, {"wa_saatlik_limit": 201}, {"wa_gunluk_limit": 0}, {"wa_gunluk_limit": 1001},
        {"wa_baslangic_saat": -1}, {"wa_baslangic_saat": 24}, {"wa_bitis_saat": 0}, {"wa_bitis_saat": 25},
        {"wa_baslangic_saat": 21}, {"wa_bitis_saat": 9}, {"wa_baslangic_saat": 12, "wa_bitis_saat": 12},
        {"wa_baslangic_saat": 15, "wa_bitis_saat": 10},
        {"wa_saatlik_limit": None}, {"wa_gunluk_limit": None}, {"wa_baslangic_saat": None}, {"wa_bitis_saat": None},
        {"wa_push_varsa_atla": None},
    ):
        assert (await istemci.put(AYAR, headers=yonetici, json=govde)).status_code == 422, govde
    j = (await istemci.get(AYAR, headers=yonetici)).json()
    assert (j["wa_saatlik_limit"], j["wa_gunluk_limit"], j["wa_baslangic_saat"], j["wa_bitis_saat"], j["wa_push_varsa_atla"]) == (
        50, 250, 9, 21, True
    )


async def test_ayar_guncelleme_ve_denetim(istemci, yonetici):
    r = await istemci.put(AYAR, headers=yonetici, json={
        "wa_saatlik_limit": 200, "wa_gunluk_limit": 1000, "wa_baslangic_saat": 0, "wa_bitis_saat": 24, "wa_push_varsa_atla": False,
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["wa_saatlik_limit"], j["wa_gunluk_limit"], j["wa_baslangic_saat"], j["wa_bitis_saat"], j["wa_push_varsa_atla"]) == (
        200, 1000, 0, 24, False
    )
    # Pencere kısmi güncellenir: yalnız başlangıç, mevcut bitişle karşılaştırılır.
    assert (await istemci.put(AYAR, headers=yonetici, json={"wa_baslangic_saat": 10})).json()["wa_bitis_saat"] == 24
    assert (await istemci.put(AYAR, headers=yonetici, json={"wa_bitis_saat": 10})).status_code == 422
    assert (await istemci.put(AYAR, headers=yonetici, json={"wa_bitis_saat": 11})).status_code == 200
    async with SessionLocal() as s:
        kayitlar = (await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ayar_guncellendi").order_by(DenetimKaydi.id))).scalars().all()
    assert set(kayitlar[0].detay["alanlar"]) == {
        "wa_saatlik_limit", "wa_gunluk_limit", "wa_baslangic_saat", "wa_bitis_saat", "wa_push_varsa_atla"
    }
    assert kayitlar[1].detay["alanlar"] == ["wa_baslangic_saat"]
    # Değişmeyen değer denetim kaydı yazmaz.
    n = len(kayitlar)
    await istemci.put(AYAR, headers=yonetici, json={"wa_gunluk_limit": 1000})
    async with SessionLocal() as s:
        assert len((await s.execute(select(DenetimKaydi).where(DenetimKaydi.islem == "ayar_guncellendi"))).scalars().all()) == n
    # Kulüp iletişim / tanıtım uç noktaları WhatsApp ayarlarını sızdırmaz.
    assert "wa_saatlik_limit" not in (await istemci.get(f"{AYAR}/tanitim")).json()


# ---------- duyuru WhatsApp kabulü ve durum uç noktası ----------


async def test_duyuru_whatsapp_baglantiyken_kabul_edilir(istemci, yonetici, evolution):
    k = await veli_hesabi("v@kulup.com")
    await ogrenci("Ada", kullanici_id=k)
    await ogrenci("Ela")  # hesapsız, WhatsApp izinli
    y = await istemci.post("/api/duyurular", headers=yonetici, json={
        "baslik": "Ders iptali", "metin": "Yarın ders yok.", "hedef": TUM,
        "kanallar": {"push": True, "whatsapp": True}, "her_iki_kanal": True,
    })
    assert y.status_code == 201, y.text
    d = y.json()
    assert d["kanallar"] == {"push": True, "whatsapp": True} and d["her_iki_kanal"] is True
    assert d["istatistik"]["whatsapp"] == {"toplam": 2, "gonderildi": 0, "bekliyor": 2, "hata": 0, "iptal": 0}
    assert d["istatistik"]["push"]["bekliyor"] == 1
    async with SessionLocal() as s:
        kayit = (await s.execute(select(Duyuru))).scalar_one()
        assert kayit.kanal_whatsapp is True and kayit.her_iki_kanal is True
    assert len([b for b in await bildirimler() if b.kanal == BildirimKanal.whatsapp]) == 2
    # Listede de kanal başına sonuç ve bayrak döner.
    liste = (await istemci.get("/api/duyurular", headers=yonetici)).json()
    assert liste[0]["her_iki_kanal"] is True and liste[0]["istatistik"]["whatsapp"]["toplam"] == 2


async def test_duyuru_yalniz_whatsapp_ve_alici_yok(istemci, yonetici, evolution):
    await ogrenci("Ela")  # hesapsız: push alıcısı yok ama WhatsApp var
    y = await gonder(istemci, yonetici, TUM, kanallar={"push": False, "whatsapp": True})
    assert y.status_code == 201, y.text
    d = y.json()
    assert d["her_iki_kanal"] is False and d["istatistik"]["push"]["toplam"] == 0 and d["istatistik"]["whatsapp"]["toplam"] == 1
    # Push + WhatsApp seçili, push alıcısı yok: yine kabul (WhatsApp alıcısı var).
    assert (await gonder(istemci, yonetici, TUM, baslik="B", kanallar={"push": True, "whatsapp": True})).status_code == 201
    # WhatsApp izni olan kimse yoksa 422.
    async with SessionLocal() as s:
        await s.execute(update(IletisimKisisi).values(whatsapp_izni=False))
        await s.commit()
    y = await gonder(istemci, yonetici, TUM, baslik="C", kanallar={"push": False, "whatsapp": True})
    assert y.status_code == 422 and y.json()["detail"] == "WhatsApp alacak veli yok"


async def test_duyuru_whatsapp_koptuysa_422(istemci, yonetici, evolution):
    await ogrenci("Ela")
    evolution.durum = "close"
    y = await gonder(istemci, yonetici, TUM, kanallar={"push": False, "whatsapp": True})
    assert y.status_code == 422 and y.json()["detail"] == "WhatsApp bağlı değil"
    # Yalnız push seçiliyse WhatsApp durumu önemsenmez (ve Evolution'a hiç sorulmaz).
    evolution.istekler.clear()
    k = await veli_hesabi("v@kulup.com")
    await ogrenci("Ada", kullanici_id=k)
    assert (await gonder(istemci, yonetici, TUM)).status_code == 201
    assert evolution.istekler == []


async def test_whatsapp_durumu_devre_kesici_ve_bekleyen_sayisi(istemci, yonetici, evolution, monkeypatch):
    from app.api import whatsapp as wa_api

    monkeypatch.setattr(wa_api, "simdi", lambda: S + timedelta(minutes=3))
    await kur()
    j = (await istemci.get("/api/whatsapp", headers=yonetici)).json()
    assert j["durum"] == "bagli" and j["bekleyen_sayisi"] == 1 and j["devre_kesici"] == {"acik": False, "sebep": None}
    evolution.gonder_modu = "baglanti"
    for ad in ("Ela", "Can"):
        await kur(ad)
    for i in range(3):
        await calistir(S + timedelta(seconds=40 * i))
    j = (await istemci.get("/api/whatsapp", headers=yonetici)).json()
    assert j["devre_kesici"] == {"acik": True, "sebep": "WhatsApp servisi hatası"} and j["bekleyen_sayisi"] == 3


async def test_bildirim_listesi_kanal_filtresi(istemci, yonetici):
    await kur()
    for kanal, adet in (("whatsapp", 1), ("push", 1)):
        j = (await istemci.get("/api/bildirim-yonetimi", params={"kanal": kanal}, headers=yonetici)).json()
        assert j["toplam"] == adet and all(k["kanal"] == kanal for k in j["kayitlar"])


async def test_izinli_liste_disindaki_numaraya_gonderilmez(evolution, monkeypatch):
    await kur()
    monkeypatch.setattr(settings, "whatsapp_izinli_numaralar", "+905550000000")
    sonuc = await calistir()
    assert sonuc["gonderildi"] == 0 and sonuc["iptal"] == 1 and evolution.gonderim_sayisi == 0
    b = await tek()
    assert b.durum == BildirimDurum.iptal and b.hata == "izinli numara listesinde değil"
    assert "5551112233" not in (b.hata or "")


async def test_izinli_listedeki_numaraya_gonderilir(evolution, monkeypatch):
    await kur()
    monkeypatch.setattr(settings, "whatsapp_izinli_numaralar", "+905550000000, +905551112233")
    sonuc = await calistir()
    assert sonuc["gonderildi"] == 1 and evolution.gonderim_sayisi == 1
