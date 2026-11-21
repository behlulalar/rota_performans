import type { DevamOzeti as Ozet } from "../api/devam";
import { tarihBicimle } from "../lib/dogrulama";
import { SEBEP_AD, SEBEPLER, sebepRozeti } from "../lib/sebep";
import { rozetHata, rozetUyari } from "../lib/stil";

/** Art arda bu kadar devamsızlıkta uyarı çıkar. */
export const UYARI_ESIGI = 2;

/** Orana göre renk: %80+ iyi, %60+ dikkat, altı düşük. */
function oranRengi(oran: number | null): string {
  if (oran === null) return "text-metin-soluk";
  return oran >= 80 ? "text-basari" : oran >= 60 ? "text-uyari" : "text-hata";
}

/** Son dersler: soldan sağa eskiden yeniye; yeşil geldi, kırmızı gelmedi; telafi sarı, ek ders mavi halkalı. */
export function DevamNoktalari({ d, buyuk = false }: { d: Ozet; buyuk?: boolean }) {
  if (d.son_dersler.length === 0) return null;
  const boyut = buyuk ? "size-3.5" : "size-2.5";
  return (
    <span className="inline-flex items-center gap-1" aria-label={`Son ${d.son_dersler.length} ders`}>
      {[...d.son_dersler].reverse().map((s, i) => (
        <span
          key={i}
          title={`${tarihBicimle(s.tarih)} · ${s.durum === "geldi" ? "Geldi" : s.sebep ? `Gelmedi · ${SEBEP_AD[s.sebep]}` : "Gelmedi"}${s.telafi_mi ? " (telafi)" : s.ek_ders_mi ? " (ek ders)" : ""} · ${s.grup_ad}`}
          className={`${boyut} rounded-full ${s.durum === "geldi" ? "bg-basari" : "bg-hata"} ${s.telafi_mi ? "ring-2 ring-altin ring-offset-1 ring-offset-yuzey" : s.ek_ders_mi ? "ring-2 ring-birincil ring-offset-1 ring-offset-yuzey" : ""}`}
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
      <GelmediSebepleri d={d} />
      <SonDevamsizliklar d={d} />
    </div>
  );
}

/** Tüm gelmedi kayıtlarının sebebe göre dağılımı (API verdiyse). */
function GelmediSebepleri({ d }: { d: Ozet }) {
  const s = d.gelmedi_sebepleri;
  if (!s || d.gelmedi === 0) return null;
  return (
    <div>
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk mb-2">Gelmeme sebepleri</h3>
      <ul className="flex flex-wrap gap-2" data-testid="gelmedi-sebepleri">
        {SEBEPLER.map((x) => (
          <li key={x.anahtar} className="rounded-[10px] border border-cizgi px-3 py-1.5 text-[13px]">
            {x.ad} <span className="num font-semibold ml-1">{s[x.anahtar]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Son derslerdeki devamsızlıklar ve sebepleri. */
function SonDevamsizliklar({ d }: { d: Ozet }) {
  const l = d.son_dersler.filter((x) => x.durum === "gelmedi");
  if (l.length === 0) return null;
  return (
    <div>
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk mb-2">Son devamsızlıklar</h3>
      <ul className="divide-y divide-cizgi border-y border-cizgi" data-testid="son-devamsizliklar">
        {l.map((x, i) => (
          <li key={i} className="py-2 flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="num">{tarihBicimle(x.tarih)} <span className="text-metin-soluk">· {x.grup_ad}</span></span>
            {x.sebep && <span className={sebepRozeti(x.sebep)}>{SEBEP_AD[x.sebep]}</span>}
            {x.aciklama && <p className="basis-full text-xs text-metin-soluk" data-testid="devamsizlik-aciklama">{x.aciklama}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
