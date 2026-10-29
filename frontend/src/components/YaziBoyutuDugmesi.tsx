import { useEffect, useRef, useState } from "react";
import YaziBoyutuSecici from "./YaziBoyutuSecici";

/** Koyu şeritte "Aa" düğmesi; yazı boyutu seçiciyi küçük bir açılır pencerede gösterir. */
export default function YaziBoyutuDugmesi({ sinif = "" }: { sinif?: string }) {
  const [acik, setAcik] = useState(false);
  const kap = useRef<HTMLDivElement>(null);
  const dugme = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!acik) return;
    const disTik = (e: PointerEvent) => {
      if (kap.current && !kap.current.contains(e.target as Node)) setAcik(false);
    };
    const tus = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setAcik(false);
        dugme.current?.focus();
      }
    };
    document.addEventListener("pointerdown", disTik);
    window.addEventListener("keydown", tus);
    return () => {
      document.removeEventListener("pointerdown", disTik);
      window.removeEventListener("keydown", tus);
    };
  }, [acik]);

  return (
    <div ref={kap} className={`relative ${sinif}`}>
      <button
        ref={dugme}
        type="button"
        onClick={() => setAcik((a) => !a)}
        aria-label="Yazı boyutu"
        title="Yazı boyutu"
        aria-expanded={acik}
        aria-haspopup="dialog"
        className="grid place-items-center size-11 rounded-[10px] font-display text-[16px] leading-none text-serit-ikon hover:text-serit-ikon-secili transition-colors"
      >
        Aa
      </button>
      {acik && (
        <div
          role="dialog"
          aria-label="Yazı boyutu"
          className="fixed inset-x-3 top-[3.75rem] md:absolute md:inset-x-auto md:right-0 md:top-full md:mt-2 md:w-72 z-40 p-3 rounded-[14px] bg-yuzey border border-cizgi-guclu text-metin shadow-lg"
        >
          <p className="mb-2 text-[13px] text-metin-soluk">Yazı boyutu (yalnızca bu cihazda)</p>
          <YaziBoyutuSecici />
        </div>
      )}
    </div>
  );
}
