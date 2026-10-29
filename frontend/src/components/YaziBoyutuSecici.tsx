import { useYaziBoyutu, YAZI_BOYUTLARI } from "../lib/yaziBoyutu";

const HARF_BOYUTU = ["text-[12px]", "text-[15px]", "text-[18px]", "text-[22px]"];

/** Yazı boyutu seçici: 4 düğme; seçim anında uygulanır (canlı önizleme). */
export default function YaziBoyutuSecici({ sinif = "" }: { sinif?: string }) {
  const { boyut, sec } = useYaziBoyutu();
  return (
    <div role="group" aria-label="Yazı boyutu" className={`grid grid-cols-4 gap-2 ${sinif}`}>
      {YAZI_BOYUTLARI.map((b, i) => {
        const secili = b.deger === boyut;
        return (
          <button
            key={b.deger}
            type="button"
            aria-pressed={secili}
            onClick={() => sec(b.deger)}
            className={`flex flex-col items-center justify-end gap-1 min-h-14 px-1 py-2 rounded-[10px] border transition-colors ${
              secili ? "border-altin bg-altin/10 text-altin-metin font-semibold" : "border-cizgi-guclu text-metin hover:border-altin"
            }`}
          >
            <span aria-hidden="true" className={`${HARF_BOYUTU[i]} font-display leading-none`}>A</span>
            <span className="text-[12px] leading-tight text-center">{b.ad}</span>
          </button>
        );
      })}
    </div>
  );
}
