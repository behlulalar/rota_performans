// Çıplak alan adına (rotaperformans.com) kurulmuş eski PWA için kendini kaldıran servis işçisi.
// Uygulama artık panel alt alan adlarında; eski kurulumlar bu dosyayı alınca temizlenip veli adresine yönlenir.
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (olay) => {
  olay.waitUntil((async () => {
    try {
      const anahtarlar = await caches.keys();
      await Promise.all(anahtarlar.map((a) => caches.delete(a)));
    } catch (_) { /* önbellek yoksa geç */ }
    try {
      await self.registration.unregister();
    } catch (_) { /* yoksay */ }
    try {
      const istemciler = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      await Promise.all(istemciler.map((i) => i.navigate('https://veli.rotaperformans.com/').catch(() => {})));
    } catch (_) { /* yoksay */ }
  })());
});
