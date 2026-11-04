// Service worker kaydı ve güncelleme akışı. Yalnızca üretim derlemesinde çalışır (geliştirme ve e2e etkilenmez).

export const YENI_SURUM_OLAYI = "rota-yeni-surum";

// Sayfa yalnızca kullanıcı "Yenile"ye bastıysa yeniden yüklenir; ilk kurulumdaki devralma sayfayı bozmaz.
let yenilemeIstendi = false;

/** Bekleyen service worker'ı etkinleştirir; devreye girince sayfa bir kez yenilenir. */
function uygula(kayit: ServiceWorkerRegistration) {
  yenilemeIstendi = true;
  kayit.waiting?.postMessage({ tip: "SKIP_WAITING" });
}

function yeniSurumBildir(kayit: ServiceWorkerRegistration) {
  window.dispatchEvent(new CustomEvent(YENI_SURUM_OLAYI, { detail: { uygula: () => uygula(kayit) } }));
}

export function serviceWorkerKaydet(): void {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;

  let yenilendi = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!yenilemeIstendi || yenilendi) return;
    yenilendi = true;
    window.location.reload();
  });

  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((kayit) => {
        if (kayit.waiting && navigator.serviceWorker.controller) yeniSurumBildir(kayit);
        kayit.addEventListener("updatefound", () => {
          const yeni = kayit.installing;
          yeni?.addEventListener("statechange", () => {
            if (yeni.state === "installed" && navigator.serviceWorker.controller) yeniSurumBildir(kayit);
          });
        });
        // Uzun açık kalan uygulamalar da yeni sürümü fark etsin: saatte bir ve uygulamaya dönünce kontrol.
        const kontrol = () => void kayit.update().catch(() => {});
        window.setInterval(kontrol, 60 * 60 * 1000);
        document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && kontrol());
      })
      .catch(() => {
        /* kayıt başarısızsa uygulama normal çalışmaya devam eder */
      });
  });
}
