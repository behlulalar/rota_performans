import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { bugunGetir, type BugunDers, type BugunYaniti } from "../api/antrenorPaneli";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { saat } from "../lib/program";
import { birincilDugme, dugme, rozetBasari, rozetHata, rozetNotr, rozetUyari, uyariKutusu } from "../lib/stil";
import { tarihCoz } from "../lib/tarih";

const YENILEME_MS = 60_000;
const ERKEN_ACILIS_DK = 15;

/** "Perşembe, 29 Ekim" */
function gunBasligi(tarih: string): string {
  const d = tarihCoz(tarih);
  return `${d.toLocaleDateString("tr-TR", { weekday: "long" })}, ${d.toLocaleDateString("tr-TR", { day: "numeric", month: "long" })}`;
}

/** Yoklamanın açılacağı saat: ders başlangıcından 15 dakika önce. */
function acilisSaati(baslangic: string): string {
  const [s, d] = baslangic.split(":").map(Number);
  const toplam = (s * 60 + d - ERKEN_ACILIS_DK + 1440) % 1440;
  return `${String(Math.floor(toplam / 60)).padStart(2, "0")}:${String(toplam % 60).padStart(2, "0")}`;
}

function DurumRozeti({ d }: { d: BugunDers }) {
  if (d.durum === "iptal") return <span className={rozetNotr}>İptal</span>;
  if (d.yoklama_durumu === "alindi") return <span className={rozetBasari}>Alındı</span>;
  if (d.yoklama_durumu === "eksik") return <span className={rozetHata}>Eksik {d.yoklama_alinan}/{d.beklenen_ogrenci}</span>;
  return <span className={rozetUyari}>Bekliyor</span>;
}

function Kutucuk({ etiket, deger, uyari = false }: { etiket: string; deger: number; uyari?: boolean }) {
  return (
    <div className="bg-yuzey border border-cizgi rounded-[14px] px-3 py-3 min-w-0">
      <div className="text-[12px] text-metin-soluk leading-4">{etiket}</div>
      <div className={`num font-display text-[28px] leading-[1.15] mt-1 ${uyari ? "text-uyari" : ""}`}>{deger}</div>
    </div>
  );
}

function SiradakiKart({ d }: { d: BugunDers }) {
  return (
    <section className="bg-birincil border border-birincil rounded-[14px] p-5 text-birincil-metin" aria-label="Sıradaki ders">
      <div className="text-[12px] font-semibold uppercase tracking-[0.12em] opacity-75">Sıradaki ders</div>
      <div className="font-display text-[24px] leading-[1.2] mt-2 break-words">{d.grup.ad}</div>
      <div className="num text-[15px] mt-1 opacity-90">
        {saat(d.baslangic)}–{saat(d.bitis)} · {d.beklenen_ogrenci} öğrenci
        {d.telafi_sayisi > 0 ? ` (${d.telafi_sayisi} telafi)` : ""}
      </div>
      {d.yoklama_acik ? (
        <Link
          to={`/oturum/${d.id}`}
          className="mt-4 flex items-center justify-center w-full min-h-14 rounded-[12px] bg-birincil-metin text-birincil text-[16px] font-semibold hover:opacity-90 transition-opacity"
        >
          Yoklamaya git
        </Link>
      ) : (
        <>
          <div
            aria-disabled="true"
            className="mt-4 flex items-center justify-center w-full min-h-14 rounded-[12px] border border-current/40 text-[15px] font-medium opacity-80"
          >
            Yoklama {acilisSaati(d.baslangic)}'te açılır
          </div>
          <Link to={`/oturum/${d.id}`} className="mt-2 flex items-center justify-center min-h-11 text-[13px] underline underline-offset-4 opacity-80">
            Ders ayrıntısını aç
          </Link>
        </>
      )}
    </section>
  );
}

function DersSatiri({ d, tarihli = false }: { d: BugunDers; tarihli?: boolean }) {
  const iptal = d.durum === "iptal";
  return (
    <Link
      to={`/oturum/${d.id}`}
      className={`flex items-center gap-3 px-4 py-3 min-h-16 hover:bg-yuzey-yuksek transition-colors ${iptal ? "opacity-60" : ""}`}
    >
      <div className="num w-[4.5rem] shrink-0 text-[15px] font-semibold leading-tight">
        {tarihli && <div className="text-[11px] font-normal text-metin-soluk">{tarihCoz(d.tarih).toLocaleDateString("tr-TR", { day: "numeric", month: "short" })}</div>}
        {saat(d.baslangic)}
        <div className="text-[12px] font-normal text-metin-soluk">{saat(d.bitis)}</div>
      </div>
      <div className="min-w-0 flex-1">
        <div className={`text-[15px] font-medium break-words ${iptal ? "line-through" : ""}`}>{d.grup.ad}</div>
        <div className="num text-[13px] text-metin-soluk mt-0.5">
          {d.beklenen_ogrenci} öğrenci
          {d.telafi_sayisi > 0 && <span className={`${rozetNotr} ml-2`}>{d.telafi_sayisi} telafi</span>}
        </div>
      </div>
      <DurumRozeti d={d} />
    </Link>
  );
}

export default function AntrenorBugun() {
  const [veri, setVeri] = useState<BugunYaniti | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  const yukle = useCallback(async () => {
    try {
      setVeri(await bugunGetir());
      setHata(null);
    } catch (e) {
      setHata(hataMesaji(e));
    }
  }, []);

  // İlk yükleme; sonra sayfa görünürken dakikada bir ve sekmeye dönünce yenilenir.
  useEffect(() => {
    void yukle();
    const zamanlayici = window.setInterval(() => {
      if (document.visibilityState === "visible") void yukle();
    }, YENILEME_MS);
    const gorunur = () => document.visibilityState === "visible" && void yukle();
    document.addEventListener("visibilitychange", gorunur);
    return () => {
      window.clearInterval(zamanlayici);
      document.removeEventListener("visibilitychange", gorunur);
    };
  }, [yukle]);

  const siradaki = veri?.dersler.find((d) => d.id === veri.siradaki);

  return (
    <>
      <SayfaBasligi baslik="Bugün" aciklama={veri ? gunBasligi(veri.tarih) : undefined} />
      {hata && (
        <p role="alert" className="text-sm text-hata mb-4">
          {hata}
        </p>
      )}
      {!veri && !hata && <p className="text-metin-soluk">Yükleniyor…</p>}
      {veri && (
        <div className="space-y-4 max-w-3xl">
          <div className="grid grid-cols-3 gap-2 md:gap-4">
            <Kutucuk etiket="Ders" deger={veri.ozet.ders_sayisi} />
            <Kutucuk etiket="Öğrenci" deger={veri.ozet.toplam_ogrenci} />
            <Kutucuk etiket="Yoklama bekleyen" deger={veri.ozet.yoklama_bekleyen} uyari={veri.ozet.yoklama_bekleyen > 0} />
          </div>

          {veri.eksik_yoklamalar.length > 0 && (
            <section className={`${uyariKutusu} !px-0 !py-0 overflow-hidden`} aria-label="Yoklaması alınmamış dersler">
              <h2 className="px-4 pt-3 pb-1 text-[14px] font-semibold">Yoklaması alınmamış ders</h2>
              <p className="px-4 pb-2 text-[13px] opacity-90">Son 7 günde bitmiş, yoklaması tamamlanmamış dersler.</p>
              <div className="divide-y divide-uyari/20 bg-yuzey/60 text-metin">
                {veri.eksik_yoklamalar.map((d) => (
                  <DersSatiri key={d.id} d={d} tarihli />
                ))}
              </div>
            </section>
          )}

          {siradaki && <SiradakiKart d={siradaki} />}

          {veri.dersler.length === 0 ? (
            <Kart baslik="Bugün dersiniz yok" aciklama="Yaklaşan dersleriniz için takvime bakın.">
              <Link to="/takvim" className={`${birincilDugme} w-full sm:w-auto`}>
                Takvimi aç
              </Link>
            </Kart>
          ) : (
            <Kart baslik="Bugünkü dersler" bosluksuz>
              <div className="divide-y divide-cizgi">
                {veri.dersler.map((d) => (
                  <DersSatiri key={d.id} d={d} />
                ))}
              </div>
              <div className="p-4 border-t border-cizgi">
                <Link to="/takvim" className={`${dugme} w-full sm:w-auto`}>
                  Takvimi aç
                </Link>
              </div>
            </Kart>
          )}
        </div>
      )}
    </>
  );
}
