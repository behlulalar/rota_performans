/* Rota Performans Akademi - service worker (minimal ve güvenli).
 * - Sayfa gezintileri: önce ağ, bağlantı yoksa /offline.html.
 * - Statik dosyalar (/assets/, simgeler, manifest): önce önbellek.
 * - /api/ ve diğer her şey: hiç dokunulmaz (önbelleğe alınmaz).
 */
const SURUM = "v1";
const ONBELLEK = `rota-statik-${SURUM}`;
const OFFLINE_SAYFA = "/offline.html";
const ON_YUKLEME = [OFFLINE_SAYFA, "/icon-192.png", "/manifest.webmanifest"];

self.addEventListener("install", (olay) => {
  olay.waitUntil(caches.open(ONBELLEK).then((c) => c.addAll(ON_YUKLEME)).then(() => self.skipWaiting()));
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

/* --- PUSH BİLDİRİMLERİ (Faz 4, sonraki dilim) ---
 * "push" ve "notificationclick" olay işleyicileri buraya eklenecek.
 */
