/**
 * Service Worker — Studio Legale PCT
 * Strategia:
 *   - CDN (Bootstrap, Chart.js): cache-first (immutabili)
 *   - /static/: cache-first
 *   - Navigazione app: network-first → fallback /offline
 *   - API (/api/, /sync/): network-only (dati real-time)
 */

const CACHE = 'pct-v3';

const PRECACHE = [
  '/offline',
  '/static/manifest.json',
  '/static/icons/icon.svg',
  '/static/css/app.css',
  '/static/js/push.js',
  'https://cdn.jsdelivr.net/npm/htmx.org@2.0.3/dist/htmx.min.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap',
];

/* ---- Install: pre-cacha gli asset statici ---- */
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(PRECACHE))
      .catch(() => {}) // non bloccare se CDN offline al momento del deploy
  );
  self.skipWaiting();
});

/* ---- Activate: pulisce versioni vecchie ---- */
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

/* ---- Fetch ---- */
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Solo GET
  if (request.method !== 'GET') return;
  // Non intercettare chrome-extension o altri schemi
  if (!url.protocol.startsWith('http')) return;

  // API e SSE sync: sempre network, mai cache
  if (url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/sync/') ||
      url.pathname.startsWith('/cerca')) {
    return; // lascia passare al browser
  }

  // CDN e /static/: cache-first
  if (url.hostname === 'cdn.jsdelivr.net' ||
      url.hostname === 'fonts.googleapis.com' ||
      url.hostname === 'fonts.gstatic.com' ||
      url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE).then(c => c.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // Navigazione app: network-first, fallback pagina offline
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/offline'))
    );
    return;
  }
});
