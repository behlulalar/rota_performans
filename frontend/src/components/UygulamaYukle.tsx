import { useEffect, useState } from "react";
import { birincilDugme, bilgiKutusu, dugme } from "../lib/stil";

const ANAHTAR = "rota-yukle-kapali";

// Chrome'un "beforeinstallprompt" olayı (standart tipte yok).
interface YuklemeOlayi extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function kapaliMi(): boolean {
  try {
    return localStorage.getItem(ANAHTAR) === "1";
  } catch {
    return false;
  }
}

function kuruluMu(): boolean {
  try {
    return window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
  } catch {
    return false;
  }
}

function iosSafariMi(): boolean {
  const ua = navigator.userAgent;
  const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  // iOS'ta Chrome/Firefox/Edge "Ana Ekrana Ekle" sunmaz (iOS 16.4+ Safari dışında da var ama emin olunamaz); Safari'ye odaklanılır.
  return ios && /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
}

/** Veli panelinde "Ana ekrana ekle" yönlendirmesi: kapatılabilir, kapatılınca hatırlanır. */
export default function UygulamaYukle() {
  const [kapali, setKapali] = useState(() => kapaliMi() || kuruluMu());
  const [olay, setOlay] = useState<YuklemeOlayi | null>(null);
  const [ios] = useState(() => iosSafariMi());

  useEffect(() => {
    const dinle = (e: Event) => {
      e.preventDefault();
      setOlay(e as YuklemeOlayi);
    };
    const kurulduda = () => {
      setOlay(null);
      setKapali(true);
    };
    window.addEventListener("beforeinstallprompt", dinle);
    window.addEventListener("appinstalled", kurulduda);
    return () => {
      window.removeEventListener("beforeinstallprompt", dinle);
      window.removeEventListener("appinstalled", kurulduda);
    };
  }, []);

  if (kapali || (!olay && !ios)) return null;

  function kapat() {
    setKapali(true);
    try {
      localStorage.setItem(ANAHTAR, "1");
    } catch {
      /* depolama kapalıysa yalnızca bu oturumda gizlenir */
    }
  }

  async function yukle() {
    if (!olay) return;
    try {
      await olay.prompt();
      await olay.userChoice;
    } catch {
      /* kullanıcı istemi reddetti ya da tarayıcı desteklemiyor */
    }
    setOlay(null);
  }

  return (
    <div className={`${bilgiKutusu} mb-4 flex flex-col sm:flex-row sm:items-center gap-3`} role="region" aria-label="Uygulamayı yükle">
      <p className="flex-1 min-w-0 text-[13px] leading-snug">
        {olay ? (
          <>
            <strong className="font-semibold">Rota Performans</strong> uygulamasını ana ekranınıza ekleyin; tek dokunuşla açılır.
          </>
        ) : (
          <>
            Uygulamayı ana ekranınıza ekleyin: Safari'de <strong className="font-semibold">Paylaş</strong> simgesine dokunun, sonra{" "}
            <strong className="font-semibold">"Ana Ekrana Ekle"</strong> seçeneğini seçin.
          </>
        )}
      </p>
      <div className="flex gap-2 shrink-0">
        {olay && (
          <button type="button" onClick={yukle} className={birincilDugme}>
            Uygulamayı yükle
          </button>
        )}
        <button type="button" onClick={kapat} className={dugme}>
          Kapat
        </button>
      </div>
    </div>
  );
}
