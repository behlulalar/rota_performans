import { useEffect, useRef } from "react";

/** Boşta kalma süresi. Sunucudaki BOSTA_DAKIKA ayarıyla aynı olmalı. */
export const BOSTA_DAKIKA = 30;
const BOSTA_MS = BOSTA_DAKIKA * 60_000;

const ANAHTAR = "rota-son-etkinlik";
const YAZMA_ARALIGI_MS = 5_000; // depolamaya en sık bu aralıkla yazılır
const SUNUCU_ARALIGI_MS = 60_000; // sunucuya en sık dakikada bir "hareket var" denir
const KONTROL_ARALIGI_MS = 15_000;
const HAREKET_OLAYLARI = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart", "scroll"] as const;

// Depolama kapalıysa yalnız bu sekmenin hareketi sayılır.
let bellek = Date.now();

function yaz(an: number) {
  bellek = an;
  try {
    localStorage.setItem(ANAHTAR, String(an));
  } catch {
    /* depolama kapalı olabilir */
  }
}

/** Son kullanıcı hareketi (ms). Sekmeler depolamayı paylaşır: hangi sekmede hareket olursa sayılır. */
function sonHareket(): number {
  try {
    const v = Number(localStorage.getItem(ANAHTAR));
    if (Number.isFinite(v) && v > 0) return Math.max(v, bellek);
  } catch {
    /* depolama kapalı olabilir */
  }
  return bellek;
}

/** Sunucudaki oturumun boşta süresini yeniden başlatır. Başarısızlık sessizdir: oturumu gerçekte
 * kapatmak sunucunun yenileme reddi ve aşağıdaki yerel sayacın işidir. */
async function sunucuyaBildir(): Promise<boolean> {
  try {
    const yanit = await fetch("/api/auth/etkinlik", { method: "POST", credentials: "same-origin" });
    return yanit.ok;
  } catch {
    return false;
  }
}

/**
 * Oturum açıkken kullanıcı hareketini (fare, klavye, dokunma, kaydırma) izler. BOSTA_DAKIKA boyunca
 * hareket olmazsa `kapat` çağrılır; sekme açık, arka planda ya da cihaz uykuda olsa da geçerlidir.
 * Süre sistem saatine göre ölçüldüğü için uyku/arka plan sonrası dönüşte de anında uygulanır.
 */
export function useBostaKapanma(aktif: boolean, kapat: () => void) {
  const kapatRef = useRef(kapat);
  useEffect(() => {
    kapatRef.current = kapat;
  });

  useEffect(() => {
    if (!aktif) return;
    const baslangic = Date.now();
    yaz(baslangic); // giriş ya da sayfanın açılışı da bir harekettir
    let sonYazma = baslangic;
    let sonSunucu = baslangic;
    void sunucuyaBildir();

    const kontrol = () => {
      if (Date.now() - sonHareket() >= BOSTA_MS) kapatRef.current();
    };

    const hareket = () => {
      const an = Date.now();
      // Süre zaten dolduysa hareket oturumu kurtarmaz (ör. cihaz uykudan döndü, sayaç henüz çalışmadı).
      if (an - sonHareket() >= BOSTA_MS) {
        kapatRef.current();
        return;
      }
      if (an - sonYazma >= YAZMA_ARALIGI_MS) {
        sonYazma = an;
        yaz(an);
      }
      if (an - sonSunucu >= SUNUCU_ARALIGI_MS) {
        sonSunucu = an;
        void sunucuyaBildir().then((tamam) => {
          if (!tamam) sonSunucu = Date.now() - SUNUCU_ARALIGI_MS + 10_000; // 10 sn sonra yeniden dene
        });
      }
    };

    for (const o of HAREKET_OLAYLARI) window.addEventListener(o, hareket, { passive: true, capture: true });
    const aralik = window.setInterval(kontrol, KONTROL_ARALIGI_MS);
    const gorunur = () => {
      if (document.visibilityState === "visible") kontrol();
    };
    document.addEventListener("visibilitychange", gorunur);
    window.addEventListener("focus", kontrol);
    window.addEventListener("pageshow", kontrol);
    return () => {
      for (const o of HAREKET_OLAYLARI) window.removeEventListener(o, hareket, { capture: true });
      window.clearInterval(aralik);
      document.removeEventListener("visibilitychange", gorunur);
      window.removeEventListener("focus", kontrol);
      window.removeEventListener("pageshow", kontrol);
    };
  }, [aktif]);
}
