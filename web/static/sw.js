/* IUSENTRA service worker per PWA e notifiche dispositivo.
 *
 * Non memorizza dati operativi in cache e non contiene informazioni sensibili:
 * tiene solo la pagina «Sei offline» e le icone, per mostrare un avviso chiaro
 * quando l'app installata si apre senza rete. Le pagine e le API vanno sempre
 * in rete, senza copie locali.
 */

const DEFAULT_HREF = '/app-v2';
const NOTIFICATION_ICON = '/static/icons/icon-192.png';
const NOTIFICATION_BADGE = '/static/icons/badge-96.png';
const SW_VERSION = '2026-09-29-offline-v7';
const SHELL_CACHE = `iusentra-shell-${SW_VERSION}`;
const OFFLINE_URL = '/offline';
const SHELL_ASSETS = [OFFLINE_URL, NOTIFICATION_ICON, '/static/icons/icon-512.png'];
const REMOTE_HEARING_DOMAINS = [
  'teams.microsoft.com',
  'zoom.us',
  'webex.com',
  'meet.google.com',
  'meet.jit.si',
  'gotomeeting.com',
  'global.gotomeeting.com',
  'bluejeans.com',
  'whereby.com',
  'lifesizecloud.com',
];
function safeHref(value) {
  const href = typeof value === 'string' ? value.trim() : '';
  if (!href || !href.startsWith('/') || href.startsWith('//')) return DEFAULT_HREF;
  if (/javascript:|data:|\r|\n/i.test(href)) return DEFAULT_HREF;
  return href;
}

function safeRemoteHearingUrl(value) {
  const raw = typeof value === 'string' ? value.trim() : '';
  if (!raw) return '';
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:') return '';
    const host = url.hostname.toLowerCase();
    const allowedDomain = REMOTE_HEARING_DOMAINS.some((domain) => host === domain || host.endsWith(`.${domain}`));
    return allowedDomain ? url.href : '';
  } catch (_) {
    return '';
  }
}

function parsePushPayload(event) {
  if (!event.data) return {};
  try {
    return event.data.json();
  } catch (_) {
    try {
      return JSON.parse(event.data.text());
    } catch (_) {
      return {};
    }
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    try {
      const cache = await caches.open(SHELL_CACHE);
      await cache.addAll(SHELL_ASSETS.map((url) => new Request(url, { cache: 'reload', credentials: 'same-origin' })));
    } catch (_) {
      // Senza la pagina offline in cache il service worker resta utile per le notifiche.
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const chiavi = await caches.keys();
    await Promise.all(chiavi.filter((chiave) => chiave.startsWith('iusentra-shell-') && chiave !== SHELL_CACHE)
      .map((chiave) => caches.delete(chiave)));
    await self.clients.claim();
  })());
});

self.addEventListener('push', (event) => {
  const payload = parsePushPayload(event);
  const title = typeof payload.title === 'string' && payload.title.trim() ? payload.title : 'IUSENTRA';
  const body = typeof payload.body === 'string' && payload.body.trim()
    ? payload.body
    : 'Hai una nuova notifica nel gestionale.';
  const href = safeHref(payload.href);
  const priority = typeof payload.priority === 'string' ? payload.priority : 'normal';
  const notificationId = typeof payload.notificationId === 'string' ? payload.notificationId : '';
  const remoteHearingUrl = safeRemoteHearingUrl(payload.remoteHearingUrl);
  const primaryActionTitle = href.startsWith('/scadenziario/')
    ? 'Apri scadenza'
    : href.startsWith('/agenda/')
      ? 'Apri Agenda'
      : 'Apri dettaglio';
  const actions = remoteHearingUrl
    ? [
        { action: 'open-app', title: primaryActionTitle },
        { action: 'join-hearing', title: 'Collegati' },
      ]
    : [];

  event.waitUntil(self.registration.showNotification(title, {
    body,
    icon: NOTIFICATION_ICON,
    badge: NOTIFICATION_BADGE,
    tag: notificationId || `iusentra-${priority}`,
    actions,
    data: { href, notificationId, remoteHearingUrl, version: SW_VERSION },
    renotify: true,
    requireInteraction: priority === 'urgent',
    silent: false,
    timestamp: Date.now(),
    vibrate: priority === 'urgent' ? [160, 80, 160] : [120],
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const href = safeHref(event.notification && event.notification.data && event.notification.data.href);
  const remoteHearingUrl = safeRemoteHearingUrl(
    event.notification && event.notification.data && event.notification.data.remoteHearingUrl
  );
  event.waitUntil((async () => {
    if (event.action === 'join-hearing' && remoteHearingUrl) {
      return self.clients.openWindow(remoteHearingUrl);
    }
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const targetUrl = new URL(href, self.location.origin).href;
    for (const client of windows) {
      const clientUrl = new URL(client.url);
      if (clientUrl.origin === self.location.origin) {
        if ('navigate' in client) await client.navigate(targetUrl);
        if ('focus' in client) return client.focus();
      }
    }
    return self.clients.openWindow(targetUrl);
  })());
});

// Solo le navigazioni: si prova sempre la rete; se manca, la pagina «Sei offline».
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || request.mode !== 'navigate') return;
  event.respondWith((async () => {
    try {
      return await fetch(request);
    } catch (_) {
      const cache = await caches.open(SHELL_CACHE);
      const offline = await cache.match(OFFLINE_URL);
      return offline || new Response('Sei offline: IUSENTRA richiede la connessione.', {
        status: 503,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      });
    }
  })());
});
