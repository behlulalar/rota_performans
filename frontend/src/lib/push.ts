import { pushAboneligiKaydet, pushAnahtariGetir, pushAboneliginiSil } from "../api/veli";

export type PushDurumu =
  | "kontrol" // henüz bakılmadı
  | "desteklenmiyor" // tarayıcı push desteklemiyor
  | "ios-ana-ekran" // iPhone/iPad: önce ana ekrana eklenmeli
  | "yalniz-kurulu" // service worker kayıtlı değil (geliştirme sunucusu)
  | "sunucu-kapali" // sunucuda VAPID ayarı yok
  | "reddedildi" // tarayıcı izni reddedilmiş
  | "kapali"
  | "acik";

function iosMu(): boolean {
  const ua = navigator.userAgent;
  return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function kuruluMu(): boolean {
  try {
    return window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
  } catch {
    return false;
  }
}

function destekVarMi(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/** Service worker kaydı; kayıt yoksa (geliştirme) beklemeden null döner ("ready" hiç dönmeyebilir). */
async function kayit(): Promise<ServiceWorkerRegistration | null> {
  return (await navigator.serviceWorker.getRegistration()) ?? null;
}

export async function pushDurumuBul(): Promise<PushDurumu> {
  if (!destekVarMi()) return iosMu() && !kuruluMu() ? "ios-ana-ekran" : "desteklenmiyor";
  const k = await kayit();
  if (!k) return "yalniz-kurulu";
  if (Notification.permission === "denied") return "reddedildi";
  const abonelik = await k.pushManager.getSubscription();
  return abonelik && Notification.permission === "granted" ? "acik" : "kapali";
}

function anahtarCevir(b64: string): Uint8Array<ArrayBuffer> {
  const dolgu = "=".repeat((4 - (b64.length % 4)) % 4);
  const ham = atob((b64 + dolgu).replace(/-/g, "+").replace(/_/g, "/"));
  const cikti = new Uint8Array(new ArrayBuffer(ham.length));
  for (let i = 0; i < ham.length; i++) cikti[i] = ham.charCodeAt(i);
  return cikti;
}

function b64url(tampon: ArrayBuffer | null): string {
  if (!tampon) return "";
  return btoa(String.fromCharCode(...new Uint8Array(tampon)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function cihazAdi(): string {
  const ua = navigator.userAgent;
  const os = /iPhone|iPad|iPod/.test(ua) ? "iOS" : /Android/.test(ua) ? "Android" : /Mac/.test(ua) ? "Mac" : /Windows/.test(ua) ? "Windows" : "Diğer";
  const tarayici = /CriOS|Chrome/.test(ua) ? "Chrome" : /FxiOS|Firefox/.test(ua) ? "Firefox" : /Safari/.test(ua) ? "Safari" : "Tarayıcı";
  return `${os} ${tarayici}`;
}

/** İzin ister, abone olur ve sunucuya kaydeder. Sonuçta yeni durumu verir. */
export async function pushAc(): Promise<PushDurumu> {
  const durum = await pushDurumuBul();
  if (durum !== "kapali" && durum !== "acik") return durum;
  const sunucu = await pushAnahtariGetir();
  if (!sunucu.etkin || !sunucu.anahtar) return "sunucu-kapali";
  const izin = await Notification.requestPermission();
  if (izin !== "granted") return izin === "denied" ? "reddedildi" : "kapali";
  const k = await kayit();
  if (!k) return "yalniz-kurulu";
  const abonelik =
    (await k.pushManager.getSubscription()) ??
    (await k.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: anahtarCevir(sunucu.anahtar) }));
  await pushAboneligiKaydet({
    endpoint: abonelik.endpoint,
    keys: { p256dh: b64url(abonelik.getKey("p256dh")), auth: b64url(abonelik.getKey("auth")) },
    cihaz: cihazAdi(),
  });
  return "acik";
}

export async function pushKapat(): Promise<PushDurumu> {
  const k = await kayit();
  const abonelik = k ? await k.pushManager.getSubscription() : null;
  if (abonelik) {
    await pushAboneliginiSil(abonelik.endpoint);
    await abonelik.unsubscribe();
  }
  return "kapali";
}
