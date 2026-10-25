import type { ReactNode } from "react";

/** Ortak pencere: koyu perde, başlık çubuğu ve kaydırılabilir gövde. */
export default function Modal({ baslik, onKapat, children }: { baslik: string; onKapat: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-30 bg-black/70 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label={baslik}>
      <div className="w-full max-w-md max-h-full overflow-y-auto bg-yuzey border border-cizgi-guclu rounded-[5px]">
        <div className="flex items-center justify-between px-4 min-h-11 border-b border-cizgi">
          <h2 className="font-display font-medium text-[19px] leading-6">{baslik}</h2>
          <button type="button" onClick={onKapat} className="px-2 min-h-11 text-[13px] text-metin-soluk hover:text-metin" aria-label="Kapat">Kapat</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
