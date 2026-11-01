import type { DevamOzeti as Ozet } from "../api/devam";
import { tarihBicimle } from "../lib/dogrulama";
import { rozetHata, rozetUyari } from "../lib/stil";

/** Art arda bu kadar devamsızlıkta uyarı çıkar. */
export const UYARI_ESIGI = 2;

/** Orana göre renk: %80+ iyi, %60+ dikkat, altı düşük. */
function oranRengi(oran: number | null): string {
  if (oran === null) return "text-metin-soluk";
  return oran >= 80 ? "text-basari" : oran >= 60 ? "text-uyari" : "text-hata";
}

/** Son dersler: soldan sağa eskiden yeniye; yeşil geldi, kırmızı gelmedi; telafi halkalı. */
export function DevamNoktalari({ d, buyuk = false }: { d: Ozet; buyuk?: boolean }) {
  if (d.son_dersler.length === 0) return null;
  const boyut = buyuk ? "size-3.5" : "size-2.5";
  return (
    <span className="inline-flex items-center gap-1" aria-label={`Son ${d.son_dersler.length} ders`}>
      {[...d.son_dersler].reverse().map((s, i) => (
        <span
          key={i}
          title={`${tarihBicimle(s.tarih)} · ${s.durum === "geldi" ? "Geldi" : "Gelmedi"}${s.telafi_mi ? " (telafi)" : ""} · ${s.grup_ad}`}
          className={`${boyut} rounded-full ${s.durum === "geldi" ? "bg-basari" : "bg-hata"} ${s.telafi_mi ? "ring-2 ring-altin ring-offset-1 ring-offset-yuzey" : ""}`}
        />
      ))}
    </span>
  );
}

export function DevamUyarisi({ d }: { d: Ozet }) {
  if (d.ard_arda_gelmedi < UYARI_ESIGI) return null;
  return <span className={d.ard_arda_gelmedi >= 3 ? rozetHata : rozetUyari}>Son {d.ard_arda_gelmedi} derse gelmedi</span>;
}

/** Liste satırı için kısa özet: son 30 gün oranı, noktalar, uyarı. */
export function DevamKisa({ d }: { d: Ozet }) {
  if (d.oran === null) return <span className="text-xs text-metin-soluk">Henüz yoklama yok</span>;
  const oran = d.son30_oran ?? d.oran;
  return (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className={`num text-sm font-semibold ${oranRengi(oran)}`} title={d.son30_oran !== null ? "Son 30 gün" : "Tüm zamanlar"}>%{oran}</span>
      <DevamNoktalari d={d} />
      <DevamUyarisi d={d} />
    </span>
  );
}

/** Öğrenci sayfası için ayrıntılı özet. */
export default function DevamOzeti({ d }: { d: Ozet }) {
  if (d.oran === null) return <p className="text-sm text-metin-soluk">Henüz yoklaması alınmış ders yok.</p>;
  const kutu = (baslik: string, oran: number | null, geldi: number, gelmedi: number) => (
    <div className="bg-yuzey px-4 py-3">
      <dt className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk">{baslik}</dt>
      <dd className={`num font-display text-[26px] leading-[1.15] mt-1 ${oranRengi(oran)}`}>{oran === null ? "—" : `%${oran}`}</dd>
      <dd className="num text-xs text-metin-soluk mt-0.5">{geldi} geldi · {gelmedi} gelmedi</dd>
    </div>
  );
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-px bg-cizgi border border-cizgi rounded-[10px] overflow-hidden">
        {kutu("Son 30 gün", d.son30_oran, d.son30_katildi, d.son30_gelmedi)}
        {kutu("Tüm zamanlar", d.oran, d.katildi, d.gelmedi)}
      </dl>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-[13px] text-metin-soluk">Son {d.son_dersler.length} ders <span className="text-[12px]">(eskiden yeniye)</span></div>
        <DevamNoktalari d={d} buyuk />
      </div>
      <DevamUyarisi d={d} />
    </div>
  );
}
