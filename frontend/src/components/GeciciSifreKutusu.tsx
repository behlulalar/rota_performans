import { useState } from "react";
import { birincilDugme, dugme, uyariKutusu } from "../lib/stil";

// Şifre yalnızca üst bileşenin geçici durumunda yaşar; kapatılınca üst bileşen siler.
export default function GeciciSifreKutusu({ sifre, baslik, onKapat, uyari = "Bu şifre yalnızca şimdi görünür. Antrenöre güvenli bir yoldan iletin." }: { sifre: string; baslik: string; onKapat: () => void; uyari?: string }) {
  const [kopyalandi, setKopyalandi] = useState(false);

  async function kopyala() {
    try {
      await navigator.clipboard.writeText(sifre);
      setKopyalandi(true);
    } catch {
      setKopyalandi(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 bg-black/70 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label={baslik}>
      <div className="w-full max-w-md bg-yuzey border border-cizgi-guclu rounded-[5px] p-4 space-y-4">
        <h2 className="font-display font-medium text-[19px] leading-6">{baslik}</h2>
        <div className="flex items-center gap-2">
          <code className="flex-1 min-w-0 break-all rounded-[3px] bg-zemin border border-cizgi-guclu px-3 py-2.5 font-mono text-altin-metin select-all">{sifre}</code>
          <button onClick={() => void kopyala()} className={dugme}>
            {kopyalandi ? "Kopyalandı" : "Kopyala"}
          </button>
        </div>
        <p className={uyariKutusu}>
          {uyari}
        </p>
        <div className="text-right">
          <button onClick={onKapat} className={birincilDugme}>Kapat</button>
        </div>
      </div>
    </div>
  );
}
