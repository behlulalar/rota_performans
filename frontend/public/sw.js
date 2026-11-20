/* Rota Performans Akademi - service worker (minimal ve güvenli).
 * - Sayfa gezintileri: önce ağ, bağlantı yoksa /offline.html.
 * - Statik dosyalar (/assets/, simgeler, manifest): önce önbellek.
 * - /api/ ve diğer her şey: hiç dokunulmaz (önbelleğe alınmaz).
 * - Güncelleme: yeni sürüm bekler, kullanıcı onaylayınca (SKIP_WAITING) etkinleşir.
 */
const SURUM = "v5";
const ONBELLEK = `rota-statik-${SURUM}`;
const OFFLINE_SAYFA = "/offline.html";
const ON_YUKLEME = [OFFLINE_SAYFA, "/icon-192.png", "/manifest.webmanifest"];

// Yeni sürüm hemen devreye girmez (açık bir formu/yoklamayı bozmasın): uygulama "Yenile" düğmesiyle
// SKIP_WAITING mesajı gönderince etkinleşir. İlk kurulumda zaten bekleyen sürüm yoktur.
self.addEventListener("install", (olay) => {
  olay.waitUntil(caches.open(ONBELLEK).then((c) => c.addAll(ON_YUKLEME)));
});

self.addEventListener("message", (olay) => {
  if (olay.data && olay.data.tip === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("activate", (olay) => {
  olay.waitUntil(
    caches
      .keys()
      .then((anahtarlar) => Promise.all(anahtarlar.filter((a) => a !== ONBELLEK).map((a) => caches.delete(a))))
      .then(() => self.clients.claim()),
  );
});

function statikMi(url) {
  return (
    url.pathname.startsWith("/assets/") ||
    /^\/(icon-.*|apple-touch-icon|favicon)\.png$/.test(url.pathname) ||
    url.pathname === "/manifest.webmanifest"
  );
}

self.addEventListener("fetch", (olay) => {
  const istek = olay.request;
  if (istek.method !== "GET") return;
  const url = new URL(istek.url);
  if (url.origin !== self.location.origin) return;
  // API ve kimlik bilgisi taşıyan istekler asla önbelleğe alınmaz.
  if (url.pathname.startsWith("/api/") || istek.headers.has("Authorization")) return;

  if (istek.mode === "navigate") {
    olay.respondWith(fetch(istek).catch(() => caches.match(OFFLINE_SAYFA)));
    return;
  }

  if (statikMi(url)) {
    olay.respondWith(
      caches.match(istek).then(
        (kayit) =>
          kayit ||
          fetch(istek).then((yanit) => {
            if (yanit.ok && yanit.type === "basic") {
              const kopya = yanit.clone();
              caches.open(ONBELLEK).then((c) => c.put(istek, kopya));
            }
            return yanit;
          }),
      ),
    );
  }
});

/* --- PUSH BİLDİRİMLERİ ---
 * Sunucu yükü: {baslik, govde, url, etiket}. Kişisel veri içermez; metin gönderim anında üretilir.
 */
self.addEventListener("push", (olay) => {
  let veri = {};
  try {
    veri = olay.data ? olay.data.json() : {};
  } catch {
    veri = {};
  }
  const baslik = typeof veri.baslik === "string" && veri.baslik ? veri.baslik : "Rota Performans";
  const secenekler = {
    body: typeof veri.govde === "string" ? veri.govde : "",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    data: { url: typeof veri.url === "string" ? veri.url : "/" },
  };
  if (typeof veri.etiket === "string" && veri.etiket) secenekler.tag = veri.etiket;
  olay.waitUntil(self.registration.showNotification(baslik, secenekler));
});

self.addEventListener("notificationclick", (olay) => {
  olay.notification.close();
  // Yalnızca aynı kökenli adreslere gidilir.
  let hedef = new URL("/", self.location.origin);
  try {
    const url = new URL((olay.notification.data && olay.notification.data.url) || "/", self.location.origin);
    if (url.origin === self.location.origin) hedef = url;
  } catch {
    /* geçersiz adres: ana sayfa */
  }
  olay.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((pencereler) => {
      for (const p of pencereler) {
        if (new URL(p.url).origin === self.location.origin && "focus" in p) {
          return p.focus().then((f) => (f && "navigate" in f ? f.navigate(hedef.href) : f));
        }
      }
      return self.clients.openWindow(hedef.href);
    }),
  );
});
