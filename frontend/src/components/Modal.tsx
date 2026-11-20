import { useEffect, useId, type ReactNode } from "react";

/** Ortak pencere: koyu perde, başlık çubuğu ve kaydırılabilir gövde. */
// `kolayKapanir`: Esc ve perdeye tıklama da kapatır. Yalnız bilgi pencerelerinde açılır; formlarda yanlışlıkla
// dışarı tıklanınca girilen veri kaybolmasın diye varsayılan kapalıdır.
export default function Modal({ baslik, onKapat, children, kolayKapanir = false }: { baslik: string; onKapat: () => void; children: ReactNode; kolayKapanir?: boolean }) {
  const baslikId = useId();
  useEffect(() => {
    if (!kolayKapanir) return;
    const tus = (e: KeyboardEvent) => e.key === "Escape" && onKapat();
    document.addEventListener("keydown", tus);
    return () => document.removeEventListener("keydown", tus);
  }, [onKapat, kolayKapanir]);
  return (
    <div
      className="fixed inset-0 z-30 bg-black/70 grid place-items-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={baslikId}
      onMouseDown={(e) => kolayKapanir && e.target === e.currentTarget && onKapat()}
    >
      <div className="w-full max-w-md max-h-full overflow-y-auto bg-yuzey border border-cizgi-guclu rounded-[14px]">
        <div className="flex items-center justify-between px-4 min-h-11 border-b border-cizgi">
          <h2 id={baslikId} className="font-display text-[19px] leading-6">{baslik}</h2>
          <button type="button" onClick={onKapat} className="px-2 min-h-11 text-[13px] text-metin-soluk hover:text-metin" aria-label="Kapat">Kapat</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
