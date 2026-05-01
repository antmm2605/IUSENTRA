/* IUSENTRA service worker reset.
 *
 * Le route operative non devono restare bloccate su shell React o asset
 * precedenti dopo il ripristino dei moduli storici. Questo service worker
 * prende controllo una sola volta, pulisce le cache applicative e si
 * deregistra, lasciando il browser servito direttamente dal backend Flask.
 */

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(Promise.resolve());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((key) => caches.delete(key)));
    await self.clients.claim();
    await self.registration.unregister();
    const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of clients) {
      client.postMessage({
        type: 'IUSENTRA_SW_RESET',
        message: 'Cache applicativa svuotata: le pagine operative vengono caricate dal server.',
      });
    }
  })());
});

self.addEventListener('fetch', () => {
  return undefined;
});
