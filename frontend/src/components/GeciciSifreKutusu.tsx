import { useState } from "react";

// Şifre yalnızca üst bileşenin geçici durumunda yaşar; kapatılınca üst bileşen siler.
export default function GeciciSifreKutusu({ sifre, baslik, onKapat }: { sifre: string; baslik: string; onKapat: () => void }) {
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
      <div className="w-full max-w-md bg-yuzey border border-altin/60 rounded-2xl p-5 space-y-4">
        <h2 className="font-semibold">{baslik}</h2>
        <div className="flex items-center gap-2">
          <code className="flex-1 min-w-0 break-all rounded-lg bg-zemin border border-cizgi px-3 py-2.5 text-altin-acik select-all">{sifre}</code>
          <button onClick={() => void kopyala()} className="rounded-lg border border-cizgi px-3 py-2.5 text-sm hover:border-altin">
            {kopyalandi ? "Kopyalandı" : "Kopyala"}
          </button>
        </div>
        <p className="rounded-lg border border-altin/60 bg-altin/10 text-altin-acik text-sm px-3 py-2">
          Bu şifre yalnızca şimdi görünür. Antrenöre güvenli bir yoldan iletin.
        </p>
        <div className="text-right">
          <button onClick={onKapat} className="rounded-lg bg-altin text-zemin font-semibold px-5 py-2 hover:bg-altin-acik">Kapat</button>
        </div>
      </div>
    </div>
  );
}
