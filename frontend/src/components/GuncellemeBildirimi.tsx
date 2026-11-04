import { useEffect, useState } from "react";
import { YENI_SURUM_OLAYI } from "../lib/pwa";
import { birincilDugme, dugme } from "../lib/stil";

/** Yeni sürüm hazır olduğunda alttan çıkan küçük bildirim; kullanıcı "Yenile" diyene kadar sayfa değişmez. */
export default function GuncellemeBildirimi() {
  const [uygula, setUygula] = useState<(() => void) | null>(null);
  const [gizli, setGizli] = useState(false);

  useEffect(() => {
    const dinle = (e: Event) => {
      setUygula(() => (e as CustomEvent<{ uygula: () => void }>).detail.uygula);
      setGizli(false);
    };
    window.addEventListener(YENI_SURUM_OLAYI, dinle);
    return () => window.removeEventListener(YENI_SURUM_OLAYI, dinle);
  }, []);

  if (!uygula || gizli) return null;
  return (
    <div
      role="status"
      className="fixed z-[60] inset-x-4 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] md:inset-x-auto md:right-6 md:bottom-6 md:w-96 rounded-[14px] border border-altin/60 bg-yuzey p-4 shadow-lg flex items-center gap-3"
    >
      <p className="flex-1 min-w-0 text-[13px] leading-snug">
        <strong className="font-semibold">Yeni sürüm hazır.</strong> Yenileyince güncel hâli açılır.
      </p>
      <button type="button" className={birincilDugme} onClick={uygula}>
        Yenile
      </button>
      <button type="button" className={dugme} onClick={() => setGizli(true)} aria-label="Şimdilik kapat">
        Sonra
      </button>
    </div>
  );
}
