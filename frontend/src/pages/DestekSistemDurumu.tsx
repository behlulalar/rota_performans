import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { sistemDurumuGetir, type SistemDurumu } from "../api/destek";
import OzetKarti from "../components/OzetKarti";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { dugme, kartKutusu, rozetBasari, rozetNotr } from "../lib/stil";

const YENILEME_MS = 30_000;

const saat = (d: Date) => d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

function DurumKarti({ etiket, iyi, durum, ayrinti }: { etiket: string; iyi: boolean; durum: string; ayrinti: string }) {
  return (
    <div className={`${kartKutusu} p-5 min-w-0`} data-testid="durum-karti" data-durum={iyi ? "iyi" : "kotu"}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk">{etiket}</div>
      <div className={`mt-2 flex items-center gap-2 font-display text-[24px] leading-[1.15] ${iyi ? "text-basari" : "text-hata"}`}>
        <span aria-hidden="true" className={`size-2.5 shrink-0 rounded-full ${iyi ? "bg-basari" : "bg-hata"}`} />
        {durum}
      </div>
      <div className="num text-xs mt-1 text-metin-soluk">{ayrinti}</div>
    </div>
  );
}

const gecikme = (ms: number | null) => (ms === null ? "—" : `${ms.toLocaleString("tr-TR", { maximumFractionDigits: 1 })} ms`);

function atisMetni(s: SistemDurumu["isci"]): string {
  if (!s.son_atis || s.saniye_once === null) return "Henüz atış yok";
  return `Son atış ${s.saniye_once} sn önce`;
}

export default function DestekSistemDurumu() {
  const [veri, setVeri] = useState<SistemDurumu | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [guncelleme, setGuncelleme] = useState<Date | null>(null);

  const yukle = useCallback(async () => {
    setYukleniyor(true);
    try {
      setVeri(await sistemDurumuGetir());
      setGuncelleme(new Date());
      setHata(null);
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setYukleniyor(false);
    }
  }, []);

  // Açılışta bir kez, sonra 30 sn'de bir kendiliğinden yenilenir.
  useEffect(() => {
    void yukle();
    const t = setInterval(() => void yukle(), YENILEME_MS);
    return () => clearInterval(t);
  }, [yukle]);

  const k = veri?.bildirim_kuyrugu;

  return (
    <div className="space-y-6">
      <SayfaBasligi
        baslik="Sistem durumu"
        aciklama={guncelleme ? `Son güncelleme ${saat(guncelleme)} · 30 saniyede bir yenilenir` : "Altyapı bileşenlerinin anlık durumu"}
        eylemler={
          <button className={dugme} disabled={yukleniyor} onClick={() => void yukle()}>
            {yukleniyor ? "Yenileniyor…" : "Yenile"}
          </button>
        }
      />

      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
      {!veri ? (
        !hata && <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <DurumKarti
              etiket="Veritabanı"
              iyi={veri.veritabani.ok}
              durum={veri.veritabani.ok ? "Çalışıyor" : "Yanıt yok"}
              ayrinti={veri.veritabani.ok ? `Gecikme ${gecikme(veri.veritabani.gecikme_ms)}` : "Bağlantı kurulamadı"}
            />
            <DurumKarti
              etiket="Redis"
              iyi={veri.redis.ok}
              durum={veri.redis.ok ? "Çalışıyor" : "Yanıt yok"}
              ayrinti={veri.redis.ok ? `Gecikme ${gecikme(veri.redis.gecikme_ms)}` : "Bağlantı kurulamadı"}
            />
            <DurumKarti
              etiket="Bildirim işçisi"
              iyi={veri.isci.canli}
              durum={veri.isci.canli ? "Canlı" : "Yanıt vermiyor"}
              ayrinti={atisMetni(veri.isci)}
            />
          </div>

          <section aria-labelledby="kuyruk-baslik" className="space-y-3">
            <div className="flex items-baseline justify-between gap-3">
              <h2 id="kuyruk-baslik" className="font-display text-[19px]">Bildirim kuyruğu</h2>
              <Link to="/destek/bildirimler" className="text-[13px] text-altin-metin hover:underline">Kuyruğa git</Link>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-4" data-testid="kuyruk-sayilari">
              <OzetKarti etiket="Bekliyor" deger={k!.bekliyor} ton="uyari" />
              <OzetKarti etiket="Gecikmiş" deger={k!.geciken_bekleyen} ton={k!.geciken_bekleyen > 0 ? "uyari" : "normal"} ipucu="Planlı zamanı geçmiş" />
              <OzetKarti etiket="Gönderildi" deger={k!.gonderildi} />
              <OzetKarti etiket="Hatalı" deger={k!.hata} />
              <OzetKarti etiket="İptal" deger={k!.iptal} />
            </div>
          </section>

          <section aria-labelledby="ortam-baslik" className="space-y-3">
            <h2 id="ortam-baslik" className="font-display text-[19px]">Ortam ve yapılandırma</h2>
            <dl className={`${kartKutusu} grid grid-cols-[max-content_1fr] items-center gap-x-6 gap-y-3 p-5 text-[14px]`}>
              <dt className="text-metin-soluk">Sürüm</dt>
              <dd className="num">{veri.surum}</dd>
              <dt className="text-metin-soluk">Ortam</dt>
              <dd className="num">{veri.ortam}</dd>
              <dt className="text-metin-soluk">Uygulama bildirimleri (Web Push)</dt>
              <dd><span className={veri.push_yapilandirildi ? rozetBasari : rozetNotr}>{veri.push_yapilandirildi ? "Yapılandırıldı" : "Yapılandırılmadı"}</span></dd>
              <dt className="text-metin-soluk">WhatsApp</dt>
              <dd><span className={veri.whatsapp_yapilandirildi ? rozetBasari : rozetNotr}>{veri.whatsapp_yapilandirildi ? "Yapılandırıldı" : "Yapılandırılmadı"}</span></dd>
            </dl>
          </section>
        </>
      )}
    </div>
  );
}
